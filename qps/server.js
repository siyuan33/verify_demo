const express = require("express");
const http = require("http");
const socketIo = require("socket.io");
const { Readable } = require("stream");

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

class DataGenerator extends Readable {
  constructor(options) {
    super(options);
    this.counter = 0;
    this.interval = setInterval(() => {
      this._generateData();
    }, 5);
  }

  _generateData() {
    const data = `Data ${this.counter}\n`;
    this.push(data);
    this.counter++;

    // if (this.counter >= 2000) {
    //   clearInterval(this.interval);
    //   this.push(null);
    // }
  }

  _read() {}
}

io.on("connection", (socket) => {
  console.log("A client connected");

  const dataGenerator = new DataGenerator();

  dataGenerator.on("data", (data) => {
    socket.emit("data", data.toString());
  });

  dataGenerator.on("end", () => {
    socket.disconnect(true);
  });

  socket.on("disconnect", () => {
    console.log("A client disconnected");
  });
});

const PORT = 3001;
server.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
