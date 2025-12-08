import { useState, useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";
import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import "@livekit/components-styles";
import SimpleVoiceAssistant from "./SimpleVoiceAssistant";

type LiveKitModalProps = {
  setShowSupport: Dispatch<SetStateAction<boolean>>;
};

const LiveKitModal = ({ setShowSupport }: LiveKitModalProps) => {
  const [isSubmittingName, setIsSubmittingName] = useState<boolean>(true);
  const [name, setName] = useState<string>("");
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const getToken = useCallback(async (userName: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(
        `/api/getToken?name=${encodeURIComponent(userName)}`
      );
      if (!response.ok) {
        throw new Error(`Token request failed: ${response.status}`);
      }
      const contentType = response.headers.get('content-type') || '';
      const token = contentType.includes('application/json')
        ? (await response.json())?.token
        : await response.text();
      setToken(token);
      setIsSubmittingName(false);
    } catch (error) {
      console.error(error);
      setError('Unable to connect. Please try again.');
    }
    finally { setLoading(false); }
  }, []);

  const handleNameSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (name.trim()) {
      getToken(name);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="support-room">
          {isSubmittingName ? (
            <form onSubmit={handleNameSubmit} className="name-form">
              <h2>Enter your name to connect with support</h2>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
              <button type="submit" disabled={loading}>
                {loading ? 'Connecting…' : 'Connect'}
              </button>
              <button
                type="button"
                className="cancel-button"
                onClick={() => setShowSupport(false)}
              >
                Cancel
              </button>
              {error && <div className="error-text">{error}</div>}
            </form>
          ) : token ? (
            <LiveKitRoom
              serverUrl={import.meta.env.VITE_LIVEKIT_URL}
              token={token}
              connect={true}
              video={false}
              audio={true}
              onDisconnected={() => {
                setShowSupport(false);
                setIsSubmittingName(true);
                setToken(null);
                setName("");
              }}
            >
              <RoomAudioRenderer />
              <SimpleVoiceAssistant />
            </LiveKitRoom>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default LiveKitModal;