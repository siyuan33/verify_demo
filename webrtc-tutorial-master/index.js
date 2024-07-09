let app = express();
let http_server = http.createServer(app);
http_server.listen(3333);
let io = new Server(http_server, {
  // 允许跨域访问
  cors: {
    origin: "*",
  },
});
http_server.on("listening", () => {
  let addr = http_server.address();
  if (addr) {
    let port = typeof addr === "string" ? addr : addr.port;
  }
});
