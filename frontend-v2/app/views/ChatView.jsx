import {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  Fragment,
} from "react";
import { useParams, useNavigate, useLocation } from "react-router";
import MessageBubble from "../components/MessageBubble";
import ToolCallDisplay from "../components/ToolCallDisplay";
import ProcessingStatus from "../components/ProcessingStatus";
import ReasoningDisplay from "../components/ReasoningDisplay";
import ChatInput from "../components/ChatInput";
import TodoPanel from "../components/TodoPanel";
import TokenUsageBanner from "../components/TokenUsageBanner";
import ToolsSidebar from "../components/ToolsSidebar";
import ModelSelector from "../components/ModelSelector";
import HITLToggle from "../components/HITLToggle";
import ApprovalDialog from "../components/ApprovalDialog";
import ActionsDropdown from "../components/ActionsDropdown";
import { ArrowTrendingUpIcon } from '@heroicons/react/24/outline';
import {
  PhotoIcon,
  PaperClipIcon,
  XMarkIcon,
  CodeBracketIcon,
  BugAntIcon,
  BeakerIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import { decodeJWT } from "../utils/route-permissions";

function ChatView({ authToken, onConversationChange }) {
  const { threadId: urlThreadId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const userName = useMemo(() => {
    if (!authToken) return "User";
    try {
      const payload = decodeJWT(authToken);
      return payload?.name || "User";
    } catch (e) {
      return "User";
    }
  }, [authToken]);

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  }, []);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [threadId, setThreadId] = useState(null);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [attachedImages, setAttachedImages] = useState([]);
  const [activeToolCall, setActiveToolCall] = useState(null);
  const [toolCallHistory, setToolCallHistory] = useState([]);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [processingStartTime, setProcessingStartTime] = useState(null);
  const [currentReasoning, setCurrentReasoning] = useState("");
  const [isReasoningStreaming, setIsReasoningStreaming] = useState(false);
  const [isExtractingMemories, setIsExtractingMemories] = useState(false);
  const [extractionSuccess, setExtractionSuccess] = useState(false);
  const [currentTodos, setCurrentTodos] = useState([]); // TODO tracking
  const [isInterrupted, setIsInterrupted] = useState(false);
  // Timeline for temporally accurate streaming display
  // Each entry: { id, type: 'text'|'reasoning'|'tool', content/data, timestamp, isStreaming? }
  const [streamTimeline, setStreamTimeline] = useState([]);
  const [interruptReason, setInterruptReason] = useState("");
  const [isForkingConversation, setIsForkingConversation] = useState(false);
  // Token usage tracking
  const [tokenUsage, setTokenUsage] = useState(null);
  // HITL (Human-in-the-Loop) approval state
  const [approvalRequest, setApprovalRequest] = useState(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  // TODO mode toggle
  const [useTodo, setUseTodo] = useState(false);
  // Mobile controls visibility
  const [showMobileControls, setShowMobileControls] = useState(false);
  // A2UI surfaces state - maps messageId to array of surfaces
  const [a2uiSurfaces, setA2uiSurfaces] = useState({});
  // Tools sidebar visibility
  const [showToolsSidebar, setShowToolsSidebar] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  // Track multiple concurrent streams per thread (for concurrent chat support)
  const activeStreamsRef = useRef(new Map()); // Map<threadId, AbortController>
  const initialMessageProcessed = useRef(false);
  // Store sendMessage in ref to create a stable callback for renderedMessages
  const sendMessageRef = useRef(null);

  // Debug: Log isLoading state changes
  useEffect(() => {
    console.log("[ChatView] isLoading state changed:", isLoading);
  }, [isLoading]);

  // Debug: log mount/unmount
  useEffect(() => {
    console.log("[ChatView] Component mounted with threadId:", urlThreadId);
    return () => {
      console.log(
        "[ChatView] Component unmounting, threadId was:",
        urlThreadId,
      );
    };
  }, []);

  // Fetch token usage for a conversation
  const fetchTokenUsage = useCallback(
    async (convId) => {
      try {
        const response = await fetch(`/api/conversations/${convId}/token-usage`, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });

        if (response.ok) {
          const usage = await response.json();
          setTokenUsage(usage);
        } else {
          console.warn("Failed to fetch token usage:", response.status);
          setTokenUsage(null);
        }
      } catch (error) {
        console.error("Error fetching token usage:", error);
        setTokenUsage(null);
      }
    },
    [authToken]
  );

  // Ref for aborting loadConversation requests
  const loadConversationAbortRef = useRef(null);

  // Stable loadConversation function
  const loadConversation = useCallback(
    async (convId) => {
      // Abort previous request if active
      if (loadConversationAbortRef.current) {
        loadConversationAbortRef.current.abort();
      }

      // Create new controller
      const controller = new AbortController();
      loadConversationAbortRef.current = controller;

      setIsLoading(true);
      setStreamingContent("");
      setActiveToolCall(null);
      setToolCallHistory([]);
      setTokenUsage(null); // Clear old usage while loading

      try {
        const response = await fetch(`/api/conversations/${convId}/messages`, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
          signal: controller.signal,
        });

        if (response.ok) {
          const messagesData = await response.json();
          const transformedMessages = messagesData.map((msg) => ({
            id: msg.message_id || msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp,
            attachments: msg.attachments || [],
            tool_calls: msg.tool_calls || [],
            reasoning: msg.reasoning || null,  // Include reasoning
            edited_at: msg.edited_at || null,  // Include edit timestamp
          }));

          // Extract historical tool calls from loaded messages
          const historicalToolCalls = [];
          transformedMessages.forEach((msg) => {
            if (msg.tool_calls && msg.tool_calls.length > 0) {
              msg.tool_calls.forEach((tc) => {
                historicalToolCalls.push({
                  id: tc.id,
                  name: tc.name,
                  description: tc.description,
                  args: tc.args,
                  result: tc.result,
                  isComplete: tc.is_complete,
                  parentMessageId: msg.id, // Link to parent message
                });
              });
            }
          });

          setThreadId(convId);
          setMessages(transformedMessages);
          setToolCallHistory(historicalToolCalls); // Restore historical tool calls

          // Reconstruct A2UI surfaces from render_ui tool calls
          const restoredSurfaces = {};
          transformedMessages.forEach((msg) => {
            if (msg.tool_calls && msg.tool_calls.length > 0) {
              msg.tool_calls.forEach((tc, idx) => {
                if (tc.name === 'render_ui' && tc.args) {
                  // Extract components and title from tool call args
                  const components = tc.args.components || [];
                  const title = tc.args.title;
                  if (components.length > 0) {
                    const surfaceId = `restored_${msg.id}_${idx}`;
                    if (!restoredSurfaces[msg.id]) {
                      restoredSurfaces[msg.id] = [];
                    }
                    restoredSurfaces[msg.id].push({
                      surfaceId,
                      components,
                      title,
                    });
                    console.log(`[A2UI] Restored surface ${surfaceId} for message ${msg.id}`);
                  }
                }
              });
            }
          });
          if (Object.keys(restoredSurfaces).length > 0) {
            setA2uiSurfaces(restoredSurfaces);
            console.log(`[A2UI] Restored ${Object.keys(restoredSurfaces).length} message(s) with A2UI surfaces`);
          }

          // Fetch token usage after loading messages
          fetchTokenUsage(convId);
        } else {
          console.error("Failed to load conversation:", response.status);
          setThreadId(convId);
          setMessages([]);
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          console.log("Conversation load aborted");
          return;
        }
        console.error("Error loading conversation:", error);
        setThreadId(convId);
        setMessages([]);
      } finally {
        // Only turn off loading if this is the active request
        if (loadConversationAbortRef.current === controller) {
          setIsLoading(false);
          loadConversationAbortRef.current = null;
        }
      }
    },
    [authToken, fetchTokenUsage],
  );

  // Load conversation when URL threadId changes
  useEffect(() => {
    // Always load conversation for the threadId in the URL
    // Note: urlThreadId is always present since /chat route without ID doesn't exist anymore
    if (urlThreadId) {
      loadConversation(urlThreadId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlThreadId]);

  // Don't navigate during message send - it causes remounting
  // Instead, the URL will update naturally when user clicks the conversation in sidebar

  // Auto-scroll to bottom - debounced to prevent constant reflows
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Use separate effect with throttling for scroll
  useEffect(() => {
    const timer = setTimeout(scrollToBottom, 50);
    return () => clearTimeout(timer);
  }, [messages.length, streamingContent, scrollToBottom]);

  // Memoize handlers to prevent recreation on every render
  const handleSubmit = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    // threadId is always present from URL (since /chat without ID doesn't exist)
    const allAttachments = [
      ...attachedImages.map(f => ({ file: f, type: 'image' })),
      ...attachedFiles.map(f => ({ file: f, type: 'file' }))
    ];

    sendMessage(input.trim(), threadId, false, null, allAttachments);
  }, [
    input,
    isLoading,
    attachedImages,
    attachedFiles,
    authToken,
    threadId,
    messages,
  ]);

  const sendMessage = async (messageContent, threadIdParam = null, skipUserMessage = false, messagesOverride = null, attachments = []) => {
    let finalMessageContent = messageContent;
    const uploadedFiles = [];

    // Upload all files/images to backend if provided
    if (attachments && attachments.length > 0) {
      try {
        for (const { file, type } of attachments) {
          const formData = new FormData();
          formData.append("file", file);

          const uploadEndpoint = type === 'image'
            ? "/api/upload/image"
            : "/api/upload/file";
          const uploadResponse = await fetch(uploadEndpoint, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
            body: formData,
          });

          if (!uploadResponse.ok) {
            throw new Error(`Upload failed for "${file.name}": ${uploadResponse.statusText}`);
          }

          const uploadResult = await uploadResponse.json();
          uploadedFiles.push({
            path: uploadResult.path,
            filename: uploadResult.original_filename,
            type: type
          });

          console.log("[Upload] File uploaded successfully:", uploadResult);
        }

        // Include all file references in message
        if (uploadedFiles.length > 0) {
          finalMessageContent = `${messageContent}\n\n`;
          uploadedFiles.forEach(({ filename, type, path }) => {
            finalMessageContent += `[Uploaded ${type}: ${filename}]\nFile path: ${path}\n\n`;
          });
        }
      } catch (error) {
        console.error("[Upload] Failed to upload files:", error);
        alert(`Failed to upload files: ${error.message}`);
        setIsLoading(false); // Make sure to reset loading state
        return;
      }
    }
    // Use the passed threadId parameter to avoid closure issues with React state
    const currentThreadId = threadIdParam || threadId;

    // Use messagesOverride if provided (for edit mode), otherwise use state
    let currentMessages = messagesOverride || messages;
    let userMessageId;

    if (skipUserMessage) {
      // In edit/regenerate mode: don't add a new user message, use existing messages
      // The last message in state should be the edited user message
      userMessageId = currentMessages[currentMessages.length - 1]?.id || `user_${Date.now()}`;
    } else {
      // Normal mode: create and add a new user message
      const userMessage = {
        id: `user_${Date.now()}`,
        role: "user",
        content: finalMessageContent,
        timestamp: new Date().toISOString(),
        attachments: attachments && attachments.length > 0
          ? attachments.map(a => a.type)
          : [
            ...attachedImages.map(() => "image"),
            ...attachedFiles.map(() => "file")
          ],
      };
      userMessageId = userMessage.id;

      setMessages((prev) => [...prev, userMessage]);
      // Update currentMessages to include the new user message for the API call
      currentMessages = [...currentMessages, userMessage];
    }

    setInput("");
    setIsLoading(true);
    setStreamingContent(""); // Clear any residual streaming content
    setStreamTimeline([]); // Clear timeline for new message
    setProcessingStatus("routing");
    setProcessingStartTime(Date.now());
    setAttachedImages([]);
    setAttachedFiles([]);
    setCurrentTodos([]); // Clear any previous todos
    // NOTE: Don't clear toolCallHistory here - each tool call has parentMessageId
    // so new tool calls will be properly associated with the new message.
    // Clearing this removes tool calls from previous messages in the UI.

    // Safety timeout: force cleanup after 15 minutes if stream doesn't end properly
    const safetyTimeoutId = setTimeout(() => {
      console.warn(
        "[ChatView] Safety timeout triggered - forcing cleanup after 15 minutes",
      );
      setIsLoading(false);
      setProcessingStatus(null);
      setProcessingStartTime(null);
      setCurrentTodos([]);
      setStreamTimeline([]); // Clear timeline on timeout
    }, 15 * 60 * 1000); // Increased from 5min to 15min for long operations

    // Declare these variables outside try-catch so they're accessible in finally block
    let buffer = "";
    let currentMessage = "";
    let accumulatedReasoning = ""; // Track reasoning locally (like currentMessage)
    let skippedEmptyMessageId = null; // Track messageId from skipped empty messages for tool call re-association
    let currentTextSegmentId = null; // Track current text segment in timeline for appending
    let localTimeline = []; // Track timeline locally for synchronous access when saving message

    try {
      // Create AbortController for THIS specific thread
      const controller = new AbortController();
      activeStreamsRef.current.set(currentThreadId, controller);
      console.log(`[Concurrent] Started stream for thread ${currentThreadId}, active threads:`, Array.from(activeStreamsRef.current.keys()));

      // Build messages array for API call
      // currentMessages already includes the user message (either existing or newly added)
      const allMessages = currentMessages.map((msg, idx) => ({
        role: msg.role,
        id: msg.id || `${msg.role}_${idx}`,
        content: msg.content,
      }));

      const requestData = {
        threadId: currentThreadId,
        runId: `run_${Date.now()}`,
        messages: allMessages,
        state: {},
        tools: [],
        context: [],
        forwardedProps: {},
        preferences: {
          use_todo: useTodo,
        },
      };

      const headers = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };

      if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
      }

      console.log("[ChatView] Sending message to /api/agent/ag-ui", {
        threadId: currentThreadId,
      });
      const response = await fetch("/api/agent/ag-ui", {
        method: "POST",
        headers,
        body: JSON.stringify(requestData),
        signal: controller.signal,
      });

      console.log(
        "[ChatView] Response status:",
        response.status,
        "OK:",
        response.ok,
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              console.log("[ChatView] SSE event received:", data.type);

              // Log tool-related events in detail
              if (data.type.includes("TOOL")) {
                console.log("[ChatView] Tool event details:", data);
              }

              if (data.type === "TEXT_MESSAGE_CONTENT") {
                currentMessage += data.delta;
                console.log(
                  "[ChatView] Streaming content updated, length:",
                  currentMessage.length,
                );
                setStreamingContent(currentMessage);
                setProcessingStatus("writing");

                // Update timeline with text content
                if (!currentTextSegmentId) {
                  // Create new text segment
                  currentTextSegmentId = `text_${Date.now()}`;
                  const newEntry = {
                    id: currentTextSegmentId,
                    type: 'text',
                    content: currentMessage,
                    timestamp: Date.now(),
                    isStreaming: true
                  };
                  localTimeline = [...localTimeline, newEntry];
                  setStreamTimeline(localTimeline);
                } else {
                  // Append to existing text segment
                  const segmentId = currentTextSegmentId;
                  localTimeline = localTimeline.map(entry =>
                    entry.id === segmentId
                      ? { ...entry, content: currentMessage }
                      : entry
                  );
                  setStreamTimeline(localTimeline);
                }
              } else if (data.type === "TEXT_MESSAGE_START") {
                // Track messageId from TEXT_MESSAGE_START for tool call association
                // Some models (Gemini) emit tool calls associated with this message before any content
                const startMessageId = data.messageId;
                if (startMessageId && !skippedEmptyMessageId) {
                  // Only track if we don't already have one (first empty message wins)
                  // This will be used for re-association if the message ends up empty
                  skippedEmptyMessageId = startMessageId;
                }
                setProcessingStatus("writing");
              } else if (data.type === "TEXT_MESSAGE_END") {

                // Only add message if there's actual content
                // Pydantic AI sometimes emits an empty TEXT_MESSAGE_START/END pair before reasoning
                // Some models (e.g., Gemini) send tool calls before actual message content
                if (currentMessage.trim().length > 0) {
                  const newMessageId = data.messageId || `assistant_${Date.now()}`;

                  const assistantMessage = {
                    id: newMessageId,
                    role: "assistant",
                    content: currentMessage,
                    timestamp: new Date().toISOString(),
                    reasoning: accumulatedReasoning || null, // Include reasoning if available
                    timeline: [...localTimeline], // Store timeline for temporal rendering
                  };

                  setMessages((prev) => {
                    console.log(
                      "[ChatView] Adding assistant message with",
                      currentMessage.length,
                      "chars, timeline entries:",
                      localTimeline.length,
                    );
                    return [...prev, assistantMessage];
                  });

                  // Re-associate orphaned tool calls from skipped empty message
                  // This handles models like Gemini that send tool calls before actual content
                  if (skippedEmptyMessageId) {
                    // IMPORTANT: Capture values before calling setState - the callback runs async
                    // and local variables may be modified before it executes
                    const oldMessageId = skippedEmptyMessageId;
                    const targetMessageId = newMessageId;

                    console.log(
                      "[ChatView] Re-associating tool calls from",
                      oldMessageId,
                      "to",
                      targetMessageId,
                    );
                    setToolCallHistory((prev) =>
                      prev.map((tc) =>
                        tc.parentMessageId === oldMessageId
                          ? { ...tc, parentMessageId: targetMessageId }
                          : tc,
                      ),
                    );
                    skippedEmptyMessageId = null; // Clear after re-association
                  }

                  // Transfer A2UI surfaces from streaming message ID to final message ID
                  // This ensures surfaces persist with the saved message
                  const streamingMsgId = `streaming_${currentThreadId}`;
                  setA2uiSurfaces((prev) => {
                    const streamingSurfaces = prev[streamingMsgId];
                    if (streamingSurfaces && streamingSurfaces.length > 0) {
                      console.log(
                        "[A2UI] Transferring",
                        streamingSurfaces.length,
                        "surfaces from",
                        streamingMsgId,
                        "to",
                        newMessageId,
                      );
                      const updated = { ...prev };
                      // Move surfaces to the new message ID
                      updated[newMessageId] = streamingSurfaces;
                      // Remove from streaming ID
                      delete updated[streamingMsgId];
                      return updated;
                    }
                    return prev;
                  });

                  // Persist timeline to database (fire and forget)
                  if (localTimeline.length > 0 && currentThreadId) {
                    const timelineToSave = [...localTimeline];
                    fetch(`/api/conversations/${currentThreadId}/messages/${newMessageId}/timeline`, {
                      method: 'PATCH',
                      headers: {
                        'Content-Type': 'application/json',
                        ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {})
                      },
                      body: JSON.stringify({ timeline: timelineToSave })
                    }).then(res => {
                      if (res.ok) {
                        console.log(`[Timeline] Persisted ${timelineToSave.length} entries for message ${newMessageId}`);
                      } else {
                        console.warn(`[Timeline] Failed to persist timeline: ${res.status}`);
                      }
                    }).catch(err => {
                      console.warn('[Timeline] Error persisting timeline:', err);
                    });
                  }

                  // Clear streaming state and reasoning for next message
                  setStreamingContent("");
                  setStreamTimeline([]); // Clear timeline - message now in renderedMessages
                  localTimeline = []; // Reset local timeline tracker
                  setCurrentReasoning(""); // Clear displayed reasoning
                  currentMessage = "";
                  currentTextSegmentId = null; // Reset text segment tracking
                  accumulatedReasoning = ""; // Reset reasoning for next message in run
                  console.log("[ChatView] Message added and streaming cleared");
                } else {
                  // Track the skipped message's ID for tool call re-association
                  // Some models emit tool calls associated with this empty message
                  // Only update if we don't already have a tracked ID (from TEXT_MESSAGE_START)
                  if (data.messageId && !skippedEmptyMessageId) {
                    skippedEmptyMessageId = data.messageId;
                  }
                }

                // Don't stop loading here - wait for RUN_FINISHED
                // The actual content might come after reasoning via TEXT_MESSAGE_CONTENT events
              } else if (data.type === "TODO_UPDATE") {
                // Handle TODO updates from backend
                console.log("[TODO] Received TODO_UPDATE event:", data);
                setCurrentTodos(data.todos || []);
              } else if (data.type === "SCRATCHPAD_UPDATE") {
                // Handle SCRATCHPAD updates from backend
                console.log(
                  "[SCRATCHPAD] Received SCRATCHPAD_UPDATE event:",
                  data,
                );
                // Dispatch a custom window event that ScratchpadPanel can listen to
                window.dispatchEvent(
                  new CustomEvent("scratchpadUpdate", {
                    detail: { threadId: data.threadId },
                  }),
                );
              } else if (data.type === "surfaceUpdate" || data.type === "A2UI_RENDER") {
                // Handle A2UI surface updates (v0.8 spec: surfaceUpdate, legacy: A2UI_RENDER)
                // Skip duplicate events from backend emitting both formats
                if (data.type === "A2UI_RENDER") {
                  // Legacy format - backend now emits surfaceUpdate first, skip duplicate
                  // NOTE: Must use `continue` not `return` - return exits the entire sendMessage function!
                  continue;
                }
                console.log("[A2UI] Received surfaceUpdate event:", data);
                // Always use streaming message ID during streaming so it matches the streaming MessageBubble
                const messageId = `streaming_${currentThreadId}`;
                console.log("[A2UI] Using messageId:", messageId, "(from event:", data.messageId, ")");
                setA2uiSurfaces((prev) => {
                  const updated = {
                    ...prev,
                    [messageId]: [
                      ...(prev[messageId] || []),
                      {
                        surfaceId: data.surfaceId,
                        components: data.components,
                        title: data.title,
                        dataModel: data.dataModel, // A2UI v0.8 spec: optional data model
                      },
                    ],
                  };
                  console.log("[A2UI] Updated surfaces:", updated);
                  return updated;
                });
              } else if (data.type === "dataModelUpdate") {
                // A2UI v0.8 spec: data model update
                console.log("[A2UI] Received dataModelUpdate:", data);
                // TODO: Propagate to A2UIDataProvider
              } else if (data.type === "beginRendering") {
                // A2UI v0.8 spec: signal that UI is ready
                console.log("[A2UI] Received beginRendering:", data);
              } else if (data.type === "deleteSurface" || data.type === "A2UI_DELETE") {
                // A2UI v0.8 spec: deleteSurface (legacy: A2UI_DELETE)
                console.log("[A2UI] Received deleteSurface:", data);
                setA2uiSurfaces((prev) => {
                  const newSurfaces = { ...prev };
                  // Find and remove the surface
                  for (const msgId in newSurfaces) {
                    newSurfaces[msgId] = newSurfaces[msgId].filter(
                      (s) => s.surfaceId !== data.surfaceId
                    );
                  }
                  return newSurfaces;
                });
              } else if (data.type === "A2UI_UPDATE") {
                // Handle A2UI component updates (prop updates)
                console.log("[A2UI] Received A2UI_UPDATE event:", data);
                // TODO: Implement component prop updates via dataModelUpdate
              } else if (data.type === "ERROR") {
                console.error("[ChatView] ERROR event received:", data);

                // Show error message to user
                const errorMessage = {
                  id: `error_${Date.now()}`,
                  role: "assistant",
                  content: `⚠️ **Error**: ${data.error || "An unexpected error occurred"}`,
                  timestamp: new Date().toISOString(),
                  isError: true,
                };
                setMessages((prev) => [...prev, errorMessage]);

                // Clear streaming state
                setStreamingContent("");
                setIsLoading(false);
                setActiveToolCall(null);
                setProcessingStatus(null);
                setProcessingStartTime(null);
                setCurrentReasoning("");
                setIsReasoningStreaming(false);
                setCurrentTodos([]);
              } else if (data.type === "RUN_FINISHED") {
                console.log(
                  "[ChatView] RUN_FINISHED received - cleaning up state",
                );

                // If there's remaining streaming content, add it as final message
                if (currentMessage.trim().length > 0) {
                  console.log("[ChatView] RUN_FINISHED: Adding remaining content as final message");
                  const finalMessageId = `assistant_${Date.now()}`;
                  const finalMessage = {
                    id: finalMessageId,
                    role: "assistant",
                    content: currentMessage,
                    timestamp: new Date().toISOString(),
                    reasoning: accumulatedReasoning || null, // Include reasoning
                  };
                  setMessages((prev) => [...prev, finalMessage]);

                  // Transfer A2UI surfaces from streaming message ID to final message ID
                  const streamingMsgId = `streaming_${currentThreadId}`;
                  setA2uiSurfaces((prev) => {
                    const streamingSurfaces = prev[streamingMsgId];
                    if (streamingSurfaces && streamingSurfaces.length > 0) {
                      console.log(
                        "[A2UI] RUN_FINISHED: Transferring",
                        streamingSurfaces.length,
                        "surfaces from",
                        streamingMsgId,
                        "to",
                        finalMessageId,
                      );
                      const updated = { ...prev };
                      updated[finalMessageId] = streamingSurfaces;
                      delete updated[streamingMsgId];
                      return updated;
                    }
                    return prev;
                  });

                  currentMessage = ""; // Clear local variable
                  accumulatedReasoning = ""; // Clear reasoning too
                }

                // Clear all streaming state
                setStreamingContent(""); // ← THIS WAS MISSING!
                setStreamTimeline([]); // Clear timeline on run finish
                setIsLoading(false);
                setActiveToolCall(null);
                setProcessingStatus(null);
                setProcessingStartTime(null);
                setCurrentReasoning("");
                setIsReasoningStreaming(false);
                setCurrentTodos([]);

                // Refresh token usage after message completes
                if (currentThreadId) {
                  fetchTokenUsage(currentThreadId);
                }

                // Refresh sidebar to show new/updated conversation
                onConversationChange?.();
              } else if (data.type === "TOOL_CALL_START") {
                const toolCallId = data.toolCallId || `tool_${Date.now()}`;
                const toolCall = {
                  id: toolCallId,
                  name: data.toolCallName,
                  arguments: data.toolCallArguments,
                  parentMessageId: data.parentMessageId, // Link to parent message
                  timestamp: new Date().toISOString(),
                };
                setActiveToolCall(toolCall);
                setToolCallHistory((prev) => [...prev, toolCall]);

                // Mark current text segment as no longer streaming
                if (currentTextSegmentId) {
                  const segmentId = currentTextSegmentId;
                  localTimeline = localTimeline.map(entry =>
                    entry.id === segmentId
                      ? { ...entry, isStreaming: false }
                      : entry
                  );
                  currentTextSegmentId = null; // Next text will be a new segment
                }

                // Add tool to timeline
                localTimeline = [...localTimeline, {
                  id: toolCallId,
                  type: 'tool',
                  data: { ...toolCall, status: 'running' },
                  timestamp: Date.now()
                }];
                setStreamTimeline(localTimeline);

                if (data.toolCallName?.includes("search")) {
                  setProcessingStatus("searching");
                } else if (data.toolCallName?.includes("analyze")) {
                  setProcessingStatus("analyzing");
                } else {
                  setProcessingStatus("executing_tool");
                }
              } else if (data.type === "TOOL_CALL_ARGS") {
                // Accumulate tool arguments as they stream in
                const toolCallId = data.toolCallId;
                const argsDelta = data.delta;

                setToolCallHistory((prev) =>
                  prev.map((tc) =>
                    tc.id === toolCallId
                      ? { ...tc, arguments: (tc.arguments || "") + argsDelta }
                      : tc,
                  ),
                );

                // Update timeline with new args
                localTimeline = localTimeline.map(entry =>
                  entry.id === toolCallId && entry.type === 'tool'
                    ? { ...entry, data: { ...entry.data, arguments: (entry.data.arguments || "") + argsDelta } }
                    : entry
                );
                setStreamTimeline(localTimeline);

                if (activeToolCall && activeToolCall.id === toolCallId) {
                  setActiveToolCall((prev) => ({
                    ...prev,
                    arguments: (prev.arguments || "") + argsDelta,
                  }));
                }
              } else if (data.type === "TOOL_CALL_RESULT") {
                // AG-UI sends tool results in a separate TOOL_CALL_RESULT event
                console.log(
                  "[TOOL_CALL_RESULT] Tool ID:",
                  data.toolCallId,
                  "Content:",
                  data.content,
                );
                const toolCallId = data.toolCallId;

                setToolCallHistory((prev) =>
                  prev.map((tc) =>
                    tc.id === toolCallId ? { ...tc, result: data.content } : tc,
                  ),
                );

                // Update timeline with result
                localTimeline = localTimeline.map(entry =>
                  entry.id === toolCallId && entry.type === 'tool'
                    ? { ...entry, data: { ...entry.data, result: data.content } }
                    : entry
                );
                setStreamTimeline(localTimeline);
              } else if (data.type === "TOOL_CALL_UPDATE") {
                // Update tool call with parentMessageId (for tool calls that happened before message started)
                console.log("[TOOL_CALL_UPDATE] Tool ID:", data.toolCallId, "Parent:", data.parentMessageId);
                const toolCallId = data.toolCallId;
                const parentMessageId = data.parentMessageId;

                setToolCallHistory((prev) =>
                  prev.map((tc) =>
                    tc.id === toolCallId ? { ...tc, parentMessageId } : tc,
                  ),
                );
              } else if (data.type === "TOOL_CALL_END") {
                // Mark the tool as complete
                console.log("[TOOL_CALL_END] Tool ID:", data.toolCallId);
                const toolCallId = data.toolCallId;

                setToolCallHistory((prev) =>
                  prev.map((tc) =>
                    tc.id === toolCallId ? { ...tc, isComplete: true } : tc,
                  ),
                );

                // Update timeline - mark tool as complete
                localTimeline = localTimeline.map(entry =>
                  entry.id === toolCallId && entry.type === 'tool'
                    ? { ...entry, data: { ...entry.data, isComplete: true, status: 'complete' } }
                    : entry
                );
                setStreamTimeline(localTimeline);

                // Clear active tool if this was the active one
                if (activeToolCall && activeToolCall.id === toolCallId) {
                  setActiveToolCall(null);
                }
                setProcessingStatus("thinking");
              } else if (data.type === "AGENT_ROUTING") {
                setProcessingStatus("calling_agent");
              } else if (data.type === "AGENT_SELECTED") {
                setProcessingStatus("calling_agent");
              } else if (data.type === "THINKING") {
                setProcessingStatus("thinking");
              } else if (data.type === "REASONING_START") {
                console.log("[REASONING] REASONING_START received");
                setIsReasoningStreaming(true);
                // DON'T clear reasoning - let it accumulate across multiple thinking blocks
                // setCurrentReasoning(""); // ← REMOVED to allow accumulation

                // Mark current text segment as no longer streaming
                if (currentTextSegmentId) {
                  const segmentId = currentTextSegmentId;
                  localTimeline = localTimeline.map(entry =>
                    entry.id === segmentId
                      ? { ...entry, isStreaming: false }
                      : entry
                  );
                  currentTextSegmentId = null; // Next text will be a new segment
                }

                // Add reasoning to timeline
                const reasoningId = `reasoning_${Date.now()}`;
                localTimeline = [...localTimeline, {
                  id: reasoningId,
                  type: 'reasoning',
                  content: '',
                  timestamp: Date.now(),
                  isStreaming: true
                }];
                setStreamTimeline(localTimeline);
              } else if (data.type === "REASONING_CONTENT") {
                console.log("[REASONING] REASONING_CONTENT received:", data.delta);
                const reasoningDelta = data.delta || "";
                accumulatedReasoning += reasoningDelta; // Accumulate locally
                setCurrentReasoning((prev) => prev + reasoningDelta); // Also update state for display

                // Update timeline with reasoning content
                const idx = localTimeline.findLastIndex(e => e.type === 'reasoning' && e.isStreaming);
                if (idx >= 0) {
                  localTimeline = [...localTimeline];
                  localTimeline[idx] = { ...localTimeline[idx], content: localTimeline[idx].content + reasoningDelta };
                  setStreamTimeline(localTimeline);
                }
              } else if (data.type === "REASONING_END") {
                console.log("[REASONING] REASONING_END received, total length:", currentReasoning.length);
                setIsReasoningStreaming(false);

                // Mark reasoning as complete in timeline
                localTimeline = localTimeline.map(entry =>
                  entry.type === 'reasoning' && entry.isStreaming
                    ? { ...entry, isStreaming: false }
                    : entry
                );
                setStreamTimeline(localTimeline);
              } else if (data.type === "INTERRUPTED") {
                // Handle interruption from backend
                console.log("[Interrupt] Stream interrupted:", data.reason);
                setIsInterrupted(true);
                setInterruptReason(data.reason || "Stream stopped");

                // Save partial response if any
                if (data.partial_response || currentMessage) {
                  const partialContent =
                    data.partial_response || currentMessage;
                  const assistantMessage = {
                    id: `assistant_${Date.now()}`,
                    role: "assistant",
                    content: partialContent,
                    timestamp: new Date().toISOString(),
                    reasoning: accumulatedReasoning || null, // Include reasoning even if interrupted
                    isInterrupted: true,
                  };
                  setMessages((prev) => [...prev, assistantMessage]);
                  setStreamingContent("");
                  setCurrentReasoning(""); // Clear displayed reasoning
                  currentMessage = "";
                  accumulatedReasoning = ""; // Clear reasoning
                }

                // Clean up state
                setIsLoading(false);
                setProcessingStatus(null);
                setProcessingStartTime(null);
                setActiveToolCall(null);
                setCurrentTodos([]);

                // Break out of stream reading loop
                break;
              } else if (data.type === "HITL_APPROVAL_REQUEST") {
                // HITL: User approval required for tool execution
                console.log("[HITL] Approval request received:", data);
                setApprovalRequest({
                  approvalId: data.approval_id,
                  toolName: data.tool,
                  toolArgs: data.arguments,
                  explanation: data.explanation
                });
                setShowApprovalDialog(true);
                setProcessingStatus("waiting_approval");
              } else if (data.type === "HITL_APPROVED") {
                // HITL: User approved the action
                console.log("[HITL] Approval granted:", data.approval_id);
                setShowApprovalDialog(false);
                setApprovalRequest(null);
                setProcessingStatus("executing_tool");
              } else if (data.type === "HITL_REJECTED") {
                // HITL: User rejected the action
                console.log("[HITL] Approval rejected:", data.approval_id);
                setShowApprovalDialog(false);
                setApprovalRequest(null);
                setProcessingStatus("thinking");
              } else if (data.type === "HITL_TIMEOUT") {
                // HITL: Approval request timed out
                console.log("[HITL] Approval timed out:", data.approval_id);
                setShowApprovalDialog(false);
                setApprovalRequest(null);
                setProcessingStatus("thinking");
              }
            } catch (err) {
              console.error("Failed to parse SSE data:", err);
            }
          }
        }
      }
    } catch (error) {
      if (error.name === "AbortError") {
        console.log("Request cancelled");
      } else {
        console.error("Error:", error);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Error: ${error.message}`,
            timestamp: new Date().toISOString(),
            isError: true,
          },
        ]);
      }
    } finally {
      // Clear safety timeout
      clearTimeout(safetyTimeoutId);

      console.log(
        "[ChatView] Finally block - cleaning up state, setting isLoading=false",
      );

      // If there's remaining streaming content that wasn't added as a message, add it now
      // This handles the case where TEXT_MESSAGE_CONTENT events come after TEXT_MESSAGE_END
      if (streamingContent && streamingContent.trim().length > 0) {
        console.log(
          "[ChatView] Adding remaining streaming content as final message",
        );
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant_${Date.now()}`,
            role: "assistant",
            content: streamingContent,
            timestamp: new Date().toISOString(),
            reasoning: accumulatedReasoning || null, // Include reasoning
          },
        ]);
        setStreamingContent("");
      }

      setIsLoading(false);
      setProcessingStatus(null);
      setProcessingStartTime(null);
      setCurrentTodos([]); // Also clear todos in finally block
      setStreamTimeline([]); // Clear timeline in finally block

      // Clean up the controller for THIS specific thread
      activeStreamsRef.current.delete(currentThreadId);
      console.log(`[Concurrent] Cleaned up stream for thread ${currentThreadId}, remaining threads:`, Array.from(activeStreamsRef.current.keys()));
    }
  };

  // Store sendMessage in ref for stable callback wrapper
  sendMessageRef.current = sendMessage;

  // Stable callback wrapper for sendMessage - prevents renderedMessages from re-calculating on every keystroke
  const stableSendMessage = useCallback((...args) => {
    return sendMessageRef.current?.(...args);
  }, []);

  // Handle initial message passed via navigation state
  useEffect(() => {
    if ((location.state?.initialMessage || location.state?.initialFiles || location.state?.initialImages) && !initialMessageProcessed.current && !isLoading && threadId === urlThreadId) {
      // Only send if this is a new conversation (no messages yet)
      if (messages.length === 0) {
        console.log("[ChatView] Sending initial message from navigation state");
        initialMessageProcessed.current = true;

        const allAttachments = [
          ...(location.state.initialImages || []).map(f => ({ file: f, type: 'image' })),
          ...(location.state.initialFiles || []).map(f => ({ file: f, type: 'file' }))
        ];

        setAttachedImages(location.state.initialImages || []);
        setAttachedFiles(location.state.initialFiles || []);

        sendMessage(location.state.initialMessage || "", urlThreadId, false, null, allAttachments);

        // Clear state to prevent resending on refresh/navigation
        // Use window.history.replaceState to avoid triggering React Router navigation/re-render
        try {
          const currentState = window.history.state;
          if (currentState && currentState.usr) {
            const newState = {
              ...currentState,
              usr: { ...currentState.usr, initialMessage: undefined }
            };
            window.history.replaceState(newState, '', window.location.href);
          }
        } catch (e) {
          console.error("Failed to clear initialMessage from history", e);
        }
      }
    }
  }, [isLoading, messages.length, location.state, threadId, urlThreadId, sendMessage]); // Removed navigate dependency

  const handleCancel = async () => {
    if (!threadId) {
      // No active conversation to interrupt - abort any active stream
      const currentController = activeStreamsRef.current.get(urlThreadId);
      if (currentController) {
        currentController.abort();
        activeStreamsRef.current.delete(urlThreadId);
      }
      setIsLoading(false);
      setStreamingContent("");
      setProcessingStatus(null);
      setProcessingStartTime(null);
      return;
    }

    try {
      // Call interrupt API
      const headers = {
        "Content-Type": "application/json",
      };

      if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
      }

      const response = await fetch("/api/agent/interrupt", {
        method: "POST",
        headers,
        body: JSON.stringify({
          threadId: threadId,
          reason: "User requested stop",
        }),
      });

      if (response.ok) {
        const result = await response.json();
        console.log("[Interrupt] Server response:", result);
      } else {
        console.error("[Interrupt] Failed to interrupt:", response.status);
        // Fallback to local abort for this thread
        const currentController = activeStreamsRef.current.get(threadId);
        if (currentController) {
          currentController.abort();
          activeStreamsRef.current.delete(threadId);
        }
      }
    } catch (error) {
      console.error("[Interrupt] Error calling interrupt API:", error);
      // Fallback to local abort for this thread
      const currentController = activeStreamsRef.current.get(threadId);
      if (currentController) {
        currentController.abort();
        activeStreamsRef.current.delete(threadId);
      }
    }

    // Local cleanup (will also be done when INTERRUPTED event arrives)
    setIsLoading(false);
    setStreamingContent("");
    setProcessingStatus(null);
    setProcessingStartTime(null);
  };

  const handleFileAttachment = (files) => {
    // Handle both single file and array of files
    const fileArray = Array.isArray(files) ? files : [files];
    if (fileArray.length === 0) return;

    const MAX_FILE_SIZE = 10 * 1024 * 1024;
    const MAX_IMAGE_SIZE = 10 * 1024 * 1024;

    const newImages = [];
    const newFiles = [];

    for (const file of fileArray) {
      const isImage = file.type.startsWith("image/");
      const maxSize = isImage ? MAX_IMAGE_SIZE : MAX_FILE_SIZE;

      if (file.size > maxSize) {
        const sizeInKB = (file.size / 1024).toFixed(0);
        const maxInKB = (maxSize / 1024).toFixed(0);
        alert(`File "${file.name}" is too large (${sizeInKB}KB). Maximum size is ${maxInKB}KB.`);
        continue; // Skip this file but process others
      }

      if (isImage) {
        newImages.push(file);
      } else {
        newFiles.push(file);
      }
    }

    // Add to existing attachments
    if (newImages.length > 0) {
      setAttachedImages(prev => [...prev, ...newImages]);
    }
    if (newFiles.length > 0) {
      setAttachedFiles(prev => [...prev, ...newFiles]);
    }
  };

  const removeAttachment = useCallback((type, index) => {
    if (type === 'image') {
      setAttachedImages(prev => prev.filter((_, i) => i !== index));
    } else if (type === 'file') {
      setAttachedFiles(prev => prev.filter((_, i) => i !== index));
    }
  }, []);

  const removeAllAttachments = useCallback(() => {
    setAttachedFiles([]);
    setAttachedImages([]);
  }, []);

  // Memoized callback for ChatInput - removes first attachment by type
  const handleRemoveFirstAttachment = useCallback((type) => {
    removeAttachment(type, 0);
  }, [removeAttachment]);

  const handleForkFromMessage = useCallback(async (messageId) => {
    console.log('[handleForkFromMessage] Called with messageId:', messageId);
    if (!threadId || isForkingConversation || messages.length === 0) return;

    setIsForkingConversation(true);

    try {
      const requestBody = { fork_from_message_id: messageId };
      console.log('[handleForkFromMessage] Request body:', requestBody);

      const response = await fetch(
        `/api/conversations/${threadId}/fork`,
        {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${authToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestBody),
        },
      );

      if (response.ok) {
        const result = await response.json();
        console.log(`Forked conversation from message ${messageId} to ${result.new_thread_id}`);

        // Navigate to the new forked conversation
        navigate(`/chat/${result.new_thread_id}`);

        // Trigger sidebar refresh to show new conversation
        if (onConversationChange) {
          onConversationChange();
        }
      } else {
        console.error("Failed to fork conversation:", response.status);
        alert("Failed to fork from this message. Please try again.");
      }
    } catch (error) {
      console.error("Error forking conversation:", error);
      alert("Error forking from this message. Please try again.");
    } finally {
      setIsForkingConversation(false);
    }
  }, [threadId, authToken, messages, isForkingConversation, navigate, onConversationChange]);

  // Handle editing a message (checkpoint-style: removes subsequent messages and triggers new response)
  const handleEditMessage = useCallback(async (messageId, newContent) => {
    if (!threadId || isLoading) return;

    try {
      const response = await fetch(
        `/api/conversations/${threadId}/messages/${messageId}`,
        {
          method: "PATCH",
          headers: {
            "Authorization": `Bearer ${authToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ content: newContent, checkpoint_mode: true }),
        }
      );

      if (response.ok) {
        const result = await response.json();
        console.log(`Message ${messageId} updated successfully, deleted ${result.deleted_count} subsequent messages`);

        // Find the index of the edited message
        const messageIndex = messages.findIndex((msg) => msg.id === messageId);

        if (messageIndex !== -1) {
          // Keep only messages up to and including the edited message
          // Update the edited message content and remove all subsequent messages
          const updatedMessages = messages.slice(0, messageIndex + 1).map((msg) =>
            msg.id === messageId
              ? { ...msg, content: newContent, edited_at: result.message?.edited_at || new Date().toISOString() }
              : msg
          );

          setMessages(updatedMessages);

          // Clear any streaming state
          setStreamingContent("");
          setCurrentReasoning("");
          // Only keep tool calls from messages that still exist
          const remainingMessageIds = new Set(updatedMessages.map((m) => m.id));
          setToolCallHistory((prev) =>
            prev.filter((tc) => remainingMessageIds.has(tc.parentMessageId))
          );
          setCurrentTodos([]);

          // Trigger a new response with the edited message content
          // Pass skipUserMessage=true and the updated messages array directly
          // to avoid race conditions with React state updates
          sendMessage(newContent, threadId, true, updatedMessages);
        }
      } else {
        const error = await response.json();
        console.error("Failed to edit message:", error);
        alert(error.detail || "Failed to edit message. Please try again.");
      }
    } catch (error) {
      console.error("Error editing message:", error);
      alert("Error editing message. Please try again.");
    }
  }, [threadId, authToken, messages, isLoading]);

  // Handle deleting a message (checkpoint-style: removes this message and all subsequent ones)
  const handleDeleteMessage = useCallback(async (messageId) => {
    if (!threadId) return;

    try {
      const response = await fetch(
        `/api/conversations/${threadId}/messages/${messageId}`,
        {
          method: "DELETE",
          headers: {
            "Authorization": `Bearer ${authToken}`,
          },
        }
      );

      if (response.ok) {
        const result = await response.json();
        console.log(`Message ${messageId} deleted successfully, total ${result.deleted_count} messages removed`);

        // Find the index of the deleted message and remove it + all subsequent messages
        const messageIndex = messages.findIndex((msg) => msg.id === messageId);

        // Calculate remaining messages first for tool call filtering
        let remainingMessages;
        if (messageIndex !== -1) {
          // Keep only messages before the deleted one
          remainingMessages = messages.slice(0, messageIndex);
          setMessages(remainingMessages);
        } else {
          // Fallback: just filter out the message
          remainingMessages = messages.filter((msg) => msg.id !== messageId);
          setMessages(remainingMessages);
        }

        // Clear any streaming state
        setStreamingContent("");
        setCurrentReasoning("");
        // Only keep tool calls from messages that still exist
        const remainingMessageIds = new Set(remainingMessages.map((m) => m.id));
        setToolCallHistory((prev) =>
          prev.filter((tc) => remainingMessageIds.has(tc.parentMessageId))
        );
        setCurrentTodos([]);
      } else {
        const error = await response.json();
        console.error("Failed to delete message:", error);
        alert(error.detail || "Failed to delete message. Please try again.");
      }
    } catch (error) {
      console.error("Error deleting message:", error);
      alert("Error deleting message. Please try again.");
    }
  }, [threadId, authToken, messages]);

  // Memoize message rendering to prevent re-renders on input changes
  const renderedMessages = useMemo(() => {
    return messages.map((msg, idx) => {
      // Get tools that belong to this message (for fallback/legacy messages without timeline)
      const messageTools = toolCallHistory.filter(
        (tc) => tc.parentMessageId === msg.id,
      );

      // If message has timeline, render in temporal order
      if (msg.timeline && msg.timeline.length > 0) {
        return (
          <Fragment key={msg.id || idx}>
            {msg.timeline.map((entry) => {
              switch (entry.type) {
                case 'text':
                  return (
                    <MessageBubble
                      key={entry.id}
                      message={{ ...msg, content: entry.content }}
                      isStreaming={false}
                      onForkFromHere={handleForkFromMessage}
                      onEdit={handleEditMessage}
                      onDelete={handleDeleteMessage}
                      a2uiSurfaces={a2uiSurfaces[msg.id] || []}
                      threadId={threadId}
                      onSendMessage={stableSendMessage}
                    />
                  );
                case 'reasoning':
                  return (
                    <ReasoningDisplay
                      key={entry.id}
                      reasoning={entry.content}
                      isStreaming={false}
                    />
                  );
                case 'tool':
                  return (
                    <div key={entry.id} className="max-w-3xl mx-auto px-4">
                      <ToolCallDisplay
                        toolCall={entry.data}
                        isActive={false}
                        status={entry.data.isComplete ? "success" : "pending"}
                      />
                    </div>
                  );
                default:
                  return null;
              }
            })}
          </Fragment>
        );
      }

      // Fallback: render in batched order for legacy messages without timeline
      return (
        <Fragment key={msg.id || idx}>
          {/* Show reasoning before the message if it exists */}
          {msg.reasoning && (
            <ReasoningDisplay
              reasoning={msg.reasoning}
              isStreaming={false}
            />
          )}
          {/* Render tools inline with the message that triggered them */}
          {messageTools.length > 0 && (
            <div className="max-w-3xl mx-auto px-4">
              {messageTools.map((tc) => (
                <ToolCallDisplay
                  key={tc.id}
                  toolCall={tc}
                  isActive={activeToolCall?.id === tc.id}
                  status={
                    tc.isComplete
                      ? "success"
                      : activeToolCall?.id === tc.id
                        ? "running"
                        : "pending"
                  }
                />
              ))}
            </div>
          )}
          <MessageBubble
            message={msg}
            isStreaming={false}
            onForkFromHere={handleForkFromMessage}
            onEdit={handleEditMessage}
            onDelete={handleDeleteMessage}
            a2uiSurfaces={a2uiSurfaces[msg.id] || []}
            threadId={threadId}
            onSendMessage={stableSendMessage}
          />

        </Fragment>
      );
    });
  }, [messages, toolCallHistory, activeToolCall, handleForkFromMessage, handleEditMessage, handleDeleteMessage, a2uiSurfaces, threadId, stableSendMessage]);

  const handleExtractMemories = useCallback(async () => {
    if (!threadId || isExtractingMemories) return;

    setIsExtractingMemories(true);
    setExtractionSuccess(false);

    try {
      const response = await fetch(
        `/api/conversations/${threadId}/extract-memories`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        },
      );

      if (response.ok) {
        const result = await response.json();
        console.log(`Extracted ${result.extracted_count} memories`);
        setExtractionSuccess(true);

        // Clear success message after 3 seconds
        setTimeout(() => setExtractionSuccess(false), 3000);

        // Optionally notify parent to refresh sidebar
        if (onConversationChange) {
          onConversationChange();
        }
      } else {
        console.error("Failed to extract memories:", response.status);
      }
    } catch (error) {
      console.error("Error extracting memories:", error);
    } finally {
      setIsExtractingMemories(false);
    }
  }, [threadId, authToken, isExtractingMemories, onConversationChange]);

  // HITL approval handlers
  const handleApprove = useCallback(async (approvalId) => {
    try {
      const response = await fetch('/api/hitl/respond', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          approval_id: approvalId,
          approved: true
        })
      });

      if (!response.ok) {
        console.error('Failed to send approval response:', response.status);
      } else {
        console.log('[HITL] Approval sent successfully');
      }
    } catch (error) {
      console.error('Error sending approval:', error);
    }
  }, [authToken]);

  const handleReject = useCallback(async (approvalId, reason) => {
    try {
      const response = await fetch('/api/hitl/respond', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          approval_id: approvalId,
          approved: false,
          reason: reason || 'User rejected'
        })
      });

      if (!response.ok) {
        console.error('Failed to send rejection response:', response.status);
      } else {
        console.log('[HITL] Rejection sent successfully');
      }
    } catch (error) {
      console.error('Error sending rejection:', error);
    }
  }, [authToken]);

  const handleForkConversation = useCallback(async () => {
    if (!threadId || isForkingConversation || messages.length === 0) return;

    setIsForkingConversation(true);

    try {
      const response = await fetch(
        `/api/conversations/${threadId}/fork`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${authToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}), // Empty body for full conversation fork
        },
      );

      if (response.ok) {
        const result = await response.json();
        console.log(`Forked conversation to ${result.new_thread_id}`);

        // Navigate to the new forked conversation
        navigate(`/chat/${result.new_thread_id}`);

        // Trigger sidebar refresh to show new conversation
        if (onConversationChange) {
          onConversationChange();
        }
      } else {
        console.error("Failed to fork conversation:", response.status);
        alert("Failed to fork conversation. Please try again.");
      }
    } catch (error) {
      console.error("Error forking conversation:", error);
      alert("Error forking conversation. Please try again.");
    } finally {
      setIsForkingConversation(false);
    }
  }, [threadId, authToken, messages, isForkingConversation, navigate, onConversationChange]);



  const handleSendMessage = useCallback((text) => {
    sendMessage(text);
  }, [sendMessage]);

  return (
    <div className="flex h-full flex-col bg-white dark:bg-zinc-950">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar pb-64">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full min-h-[calc(100vh-16rem)] px-4 animate-fade-in">
            <div className="flex flex-col items-center text-center space-y-6 max-w-2xl mx-auto">
              <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-sm flex items-center justify-center">
                <ArrowTrendingUpIcon className="w-12 h-12 text-white" />
              </div>

              <div className="space-y-2">
                <h1 className="text-2xl sm:text-3xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {greeting}, {userName}
                </h1>
                <p className="text-zinc-500 dark:text-zinc-400 text-lg">
                  How can I help you today?
                </p>
              </div>
            </div>
          </div>
        )}

        {renderedMessages}

        {/* Timeline-based streaming display for temporal accuracy */}
        {streamTimeline.length > 0 && (
          <div className="stream-timeline">
            {streamTimeline.map((entry, idx) => {
              const isLast = idx === streamTimeline.length - 1;

              switch (entry.type) {
                case 'text':
                  return (
                    <MessageBubble
                      key={entry.id}
                      message={{
                        id: entry.id,
                        role: "assistant",
                        content: entry.content,
                        timestamp: new Date(entry.timestamp).toISOString(),
                      }}
                      isStreaming={entry.isStreaming && isLast}
                      a2uiSurfaces={a2uiSurfaces[`streaming_${threadId}`] || []}
                      threadId={threadId}
                      onSendMessage={stableSendMessage}
                    />
                  );
                case 'reasoning':
                  return (
                    <ReasoningDisplay
                      key={entry.id}
                      reasoning={entry.content}
                      isStreaming={entry.isStreaming}
                    />
                  );
                case 'tool':
                  return (
                    <div key={entry.id} className="max-w-3xl mx-auto px-4">
                      <ToolCallDisplay
                        toolCall={entry.data}
                        isActive={entry.data.status === 'running'}
                        status={
                          entry.data.isComplete
                            ? entry.data.result ? "success" : "pending"
                            : entry.data.status === 'running'
                              ? "running"
                              : "pending"
                        }
                      />
                    </div>
                  );
                default:
                  return null;
              }
            })}
          </div>
        )}

        {/* Show processing status when no timeline entries yet */}
        {isLoading &&
          processingStatus &&
          streamTimeline.length === 0 && (
            <ProcessingStatus
              status={processingStatus}
              details={{
                agentName: activeToolCall?.name,
                toolName: activeToolCall?.name,
              }}
              startTime={processingStartTime}
            />
          )}

        {isLoading && streamTimeline.length === 0 && !processingStatus && (
          <div className="py-6 px-4 bg-zinc-50/50 dark:bg-zinc-900/50 animate-slide-in-bottom">
            <div className="max-w-3xl mx-auto">
              <div className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mb-2 px-1">
                Nifty Strategist
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-zinc-400 dark:bg-zinc-600 rounded-full animate-pulse"></div>
                <div className="w-2 h-2 bg-zinc-400 dark:bg-zinc-600 rounded-full animate-pulse animation-delay-150"></div>
                <div className="w-2 h-2 bg-zinc-400 dark:bg-zinc-600 rounded-full animate-pulse animation-delay-300"></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input - Sticky at bottom */}
      <div className="fixed bottom-0 left-0 lg:left-64 right-0 border-zinc-200 dark:border-zinc-800 bg-white/5 dark:bg-zinc-950 z-10">
        <div className="mx-auto max-w-3xl px-4 py-4">
          {/* TODO Panel - shows above input when agent is working */}
          {currentTodos && currentTodos.length > 0 && (
            <div className="mb-3">
              <TodoPanel todos={currentTodos} />
            </div>
          )}

          {/* Token Usage Banner - shows when approaching context limit */}
          {tokenUsage && messages.length > 0 && !isLoading && (
            <TokenUsageBanner
              tokenUsage={tokenUsage}
              onFork={handleForkConversation}
              isForkingConversation={isForkingConversation}
              isLoading={isLoading}
            />
          )}

          {(attachedFiles.length > 0 || attachedImages.length > 0) && (
            <div className="mb-3 animate-slide-in-bottom">
              <div className="space-y-2">
                {/* Display all attached images */}
                {attachedImages.map((image, index) => (
                  <div key={`image-${index}`} className="flex items-center justify-between p-3 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
                        <PhotoIcon className="w-4 h-4" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                          {image.name}
                        </span>
                        <span className="text-xs text-zinc-500 dark:text-zinc-400">
                          Image • {(image.size / 1024).toFixed(0)} KB
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => removeAttachment('image', index)}
                      className="p-1.5 text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                      title="Remove attachment"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}

                {/* Display all attached files */}
                {attachedFiles.map((file, index) => (
                  <div key={`file-${index}`} className="flex items-center justify-between p-3 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
                        <PaperClipIcon className="w-4 h-4" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                          {file.name}
                        </span>
                        <span className="text-xs text-zinc-500 dark:text-zinc-400">
                          File • {(file.size / 1024).toFixed(0)} KB
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => removeAttachment('file', index)}
                      className="p-1.5 text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                      title="Remove attachment"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Controls Row - Model and Actions */}
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ModelSelector authToken={authToken} compact={true} />
            </div>
            <div className="flex items-center gap-2">
              <ActionsDropdown
                onViewTools={() => setShowToolsSidebar(!showToolsSidebar)}
                onForkConversation={handleForkConversation}
                onExtractMemories={handleExtractMemories}
                isForkingConversation={isForkingConversation}
                isExtractingMemories={isExtractingMemories}
                extractionSuccess={extractionSuccess}
                useTodo={useTodo}
                onToggleTodo={() => setUseTodo(!useTodo)}
                showForkAndExtract={messages.length > 0}
                hitlComponent={<HITLToggle authToken={authToken} compact={true} />}
              />
            </div>
          </div>

          <ChatInput
            ref={textareaRef}
            value={input}
            onChange={setInput}
            onSubmit={handleSubmit}
            onFileAttach={handleFileAttachment}
            onCancel={handleCancel}
            disabled={isLoading}
            isLoading={isLoading}
            placeholder="Message Nifty Strategist..."
            attachedFile={attachedFiles[0]}
            attachedImage={attachedImages[0]}
            onRemoveAttachment={handleRemoveFirstAttachment}
            showMarkdownHints={true}
            authToken={authToken}
            recentMessages={messages}
          />

          <div className="mt-2 flex items-center justify-between px-1">
            <div className="flex items-center gap-2 text-xs text-zinc-400 dark:text-zinc-500">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 font-sans">↵</kbd>
                <span>to send</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 font-sans">⇧ ↵</kbd>
                <span>for new line</span>
              </span>
            </div>
            <div className="text-xs text-zinc-400 dark:text-zinc-500">
              AI can make mistakes. Please verify important information.
            </div>
          </div>
        </div>
      </div>

      {/* HITL Dialog */}
      {approvalRequest && (
        <ApprovalDialog
          isOpen={showApprovalDialog}
          onClose={() => setShowApprovalDialog(false)}
          onApprove={handleApprove}
          onReject={handleReject}
          toolName={approvalRequest.toolName}
          toolArgs={approvalRequest.toolArgs}
          explanation={approvalRequest.explanation}
          approvalId={approvalRequest.approvalId}
        />
      )}

      {/* Tools Sidebar */}
      <ToolsSidebar
        isOpen={showToolsSidebar}
        onClose={() => setShowToolsSidebar(false)}
        authToken={authToken}
      />
    </div>
  );
}


export default ChatView;
