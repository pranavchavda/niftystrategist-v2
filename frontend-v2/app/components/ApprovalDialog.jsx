import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import {
  Modal,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
} from './Modal';
import { Button } from './catalyst/button';

/**
 * HITL Approval Dialog Component
 *
 * Shows approval request for tool execution with approve/reject actions.
 * Uses the unified Modal component for consistent styling.
 */
export default function ApprovalDialog({
  isOpen,
  onClose,
  onApprove,
  onReject,
  toolName,
  toolArgs,
  explanation,
  approvalId
}) {
  const handleApprove = () => {
    onApprove(approvalId);
    onClose();
  };

  const handleReject = () => {
    onReject(approvalId, 'User rejected');
    onClose();
  };

  // Format tool arguments for display
  const formattedArgs = JSON.stringify(toolArgs, null, 2);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleReject}
      size="lg"
      showCloseButton={false}
      closeOnOverlayClick={false}
    >
      {/* Header */}
      <ModalHeader className="bg-amber-500/5 dark:bg-amber-500/10">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-500/20">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <ModalTitle className="text-amber-900 dark:text-amber-100">
              Approval Required
            </ModalTitle>
            <ModalDescription>
              The agent wants to execute an action that requires your approval
            </ModalDescription>
          </div>
        </div>
      </ModalHeader>

      {/* Content */}
      <ModalBody className="space-y-4">
        {/* Tool Name */}
        <div>
          <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5 uppercase tracking-wide">
            Tool
          </label>
          <div className="px-3 py-2.5 bg-zinc-100 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
            <code className="text-sm text-blue-600 dark:text-blue-400 font-mono">{toolName}</code>
          </div>
        </div>

        {/* Explanation */}
        <div>
          <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5 uppercase tracking-wide">
            What will happen
          </label>
          <div className="px-4 py-3 bg-zinc-100 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
            <p className="text-sm text-zinc-900 dark:text-zinc-100">{explanation}</p>
          </div>
        </div>

        {/* Tool Arguments */}
        {toolArgs && Object.keys(toolArgs).length > 0 && (
          <div>
            <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5 uppercase tracking-wide">
              Arguments
            </label>
            <div className="px-3 py-2 bg-zinc-950 dark:bg-zinc-950 rounded-lg border border-zinc-200 dark:border-zinc-700 max-h-48 overflow-y-auto custom-scrollbar">
              <pre className="text-xs text-zinc-300 font-mono whitespace-pre-wrap">
                {formattedArgs}
              </pre>
            </div>
          </div>
        )}

        {/* Warning */}
        <div className="flex items-start gap-3 px-4 py-3 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg">
          <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-amber-800 dark:text-amber-200/90 leading-relaxed">
            Review the action carefully before approving. Approval Mode helps you control
            what the agent can do on your behalf.
          </p>
        </div>
      </ModalBody>

      {/* Actions */}
      <ModalFooter className="flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button
            onClick={handleReject}
            outline
            className="gap-2"
          >
            <XCircle data-slot="icon" className="h-4 w-4" />
            Reject
          </Button>
          <Button
            onClick={handleApprove}
            color="blue"
            className="gap-2"
          >
            <CheckCircle data-slot="icon" className="h-4 w-4" />
            Approve & Execute
          </Button>
        </div>
        <div className="flex-1" />
        <span className="text-xs text-zinc-400 dark:text-zinc-500">
          Timeout in 60s
        </span>
      </ModalFooter>
    </Modal>
  );
}
