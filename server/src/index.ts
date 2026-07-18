import { Server } from "@colyseus/core";
import { WebSocketTransport } from "@colyseus/ws-transport";
import { GameRoom } from "./rooms/GameRoom";

const port = Number(process.env.PORT ?? 2567);

const server = new Server({
  transport: new WebSocketTransport(),
});

server.define("game", GameRoom);

server.listen(port).then(() => {
  console.log(`listening on ws://localhost:${port}`);
});
