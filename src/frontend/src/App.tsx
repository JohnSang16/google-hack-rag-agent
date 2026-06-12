import './App.css';
import { Analytics } from '@vercel/analytics/react';
import ChatInterface from './components/ChatInterface';

export default function App() {
  return (
    <>
      <ChatInterface />
      <Analytics />
    </>
  );
}
