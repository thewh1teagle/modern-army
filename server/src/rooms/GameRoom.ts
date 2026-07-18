import { Room, Client } from "@colyseus/core";
import { Schema } from "@colyseus/schema";

export class GameState extends Schema {}

export class GameRoom extends Room<GameState> {
  onCreate() {
    this.setState(new GameState());
  }

  onJoin(client: Client) {
    console.log(`${client.sessionId} joined`);
  }

  onLeave(client: Client) {
    console.log(`${client.sessionId} left`);
  }
}
