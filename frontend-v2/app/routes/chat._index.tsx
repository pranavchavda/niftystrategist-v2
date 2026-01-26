import { useOutletContext } from 'react-router';
import ChatView from '../views/ChatView';

interface AuthContext {
  authToken: string;
  onConversationChange: () => void;
}

export default function ChatIndex() {
  const { authToken, onConversationChange } = useOutletContext<AuthContext>();

  // Don't use key prop - ChatView handles state internally
  return <ChatView authToken={authToken} onConversationChange={onConversationChange} />;
}
