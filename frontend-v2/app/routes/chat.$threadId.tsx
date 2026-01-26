import { useOutletContext, useParams } from 'react-router';
import ChatView from '../views/ChatView';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
  onConversationChange: () => void;
}

export function clientLoader() {
  requirePermission('chat.access');
  return null;
}

export default function ChatThread() {
  const { authToken, onConversationChange } = useOutletContext<AuthContext>();

  // Don't use key prop - it causes remounts during message streaming
  // ChatView handles route param changes internally via useEffect
  return <ChatView authToken={authToken} onConversationChange={onConversationChange} />;
}
