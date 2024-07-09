let dataChannel;
const sendMessage = (username) => {
  const button = document.querySelector(".data-channel__button");
  const input = document.querySelector(".data-channel__input");
  button.disabled = false;
  button.onclick = () => {
    if (!input.value) return;
    const message = `${username}: ${input.value}`;
    dataChannel?.send(message);
    input.value = "";
    receiveMessage(message);
  };
};
const receiveMessage = (message) => {
  const output = document.querySelector(".data-channel__output");
  output.scrollTop = output.scrollHeight;
  output.value = output.value + message + "\r";
};
const openDataChannel = (localPc, username) => {
  dataChannel = localPc.createDataChannel("test");
  // datachannel
  dataChannel.onopen = () => sendMessage(username);
  localPc.ondatachannel = (event) => {
    // RTCDataChannel
    const dataChannel = event.channel;
    dataChannel.onmessage = (event) => receiveMessage(event.data);
  };
};

export default openDataChannel;
