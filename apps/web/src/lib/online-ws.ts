/**
 * Online game WebSocket client (online-plan §6.2).
 *
 * The socket is a transport, never an authority: server messages carry full
 * authoritative game state. If the socket dies this reconnects with backoff
 * and the page falls back to REST polling — the game stays playable.
 */
import { API_BASE } from './api-client';
import type { AchievementResponse, GameResponse } from './api-types';

export type WsEvent =
  | { type: 'game_state'; payload: GameResponse }
  | { type: 'opponent_joined'; payload: { color: string } }
  | { type: 'opponent_left'; payload: Record<string, never> }
  /** Private to this seat: achievements are never broadcast to the opponent. */
  | { type: 'achievement'; payload: { items: AchievementResponse[] } }
  | { type: 'pong'; payload: Record<string, never> }
  | { type: 'error'; payload: { detail: string } };

export type WsAction =
  | { type: 'move'; payload: { uci: string; expected_version: number } }
  | { type: 'resign' }
  | { type: 'draw_claim' }
  | { type: 'ping' };

function wsUrl(gameId: number): string {
  const origin = API_BASE ? new URL(API_BASE).origin : window.location.origin;
  return `${origin.replace(/^http/, 'ws')}/api/v1/online/ws?game_id=${gameId}`;
}

const MAX_BACKOFF_MS = 10_000;
// Server verdicts that never change by retrying: bad game id (4400), no
// session (4401), not a participant / origin rejected (4403), and the
// message-rate policy close (1008).
const NON_RETRYABLE_CLOSE = new Set([4400, 4401, 4403, 1008]);

/** Thin wrapper: auto-reconnect, heartbeat, and a single typed event callback. */
export class OnlineSocket {
  private socket: WebSocket | null = null;
  private attempts = 0;
  private closed = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private heartbeat: ReturnType<typeof setInterval> | null = null;

  constructor(
    private readonly gameId: number,
    private readonly onEvent: (event: WsEvent) => void,
    private readonly onStatus: (connected: boolean) => void,
  ) {}

  connect(): void {
    if (this.closed) return;
    // Environments without a WebSocket global cannot hold a socket open.
    if (typeof WebSocket === 'undefined') return;
    let socket: WebSocket;
    try {
      socket = new WebSocket(wsUrl(this.gameId));
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      this.attempts = 0;
      this.onStatus(true);
      this.heartbeat = setInterval(() => this.send({ type: 'ping' }), 25_000);
    };
    socket.onmessage = (msg: MessageEvent<string>) => {
      try {
        this.onEvent(JSON.parse(msg.data) as WsEvent);
      } catch {
        /* ignore malformed frames; the server never sends them */
      }
    };
    socket.onclose = (ev: CloseEvent) => {
      this.stopHeartbeat();
      this.onStatus(false);
      if (NON_RETRYABLE_CLOSE.has(ev.code)) {
        this.closed = true;
        return;
      }
      this.scheduleReconnect();
    };
    socket.onerror = () => socket.close();
  }

  send(action: WsAction): boolean {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(action));
      return true;
    }
    return false;
  }

  close(): void {
    this.closed = true;
    if (this.timer) clearTimeout(this.timer);
    this.stopHeartbeat();
    this.socket?.close();
    this.socket = null;
  }

  private stopHeartbeat(): void {
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.heartbeat = null;
  }

  private scheduleReconnect(): void {
    if (this.closed) return;
    const delay = Math.min(500 * 2 ** this.attempts, MAX_BACKOFF_MS);
    this.attempts += 1;
    this.timer = setTimeout(() => this.connect(), delay);
  }
}
