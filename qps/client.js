const io = require("socket.io-client");

const socket = io("http://localhost:3001");

socket.on("connect", () => {
  console.log("Connected to server");

  socket.on("data", (data) => {
    console.log("Received data:", data);
  });
});

socket.on("disconnect", () => {
  console.log("Disconnected from server");
});
