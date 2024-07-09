const express = require("express");
const multer = require("multer");
const path = require("path");

const app = express();
const port = 3003;

// 使用 Multer 处理文件上传
const storage = multer.memoryStorage();
const upload = multer({ storage });
app.get("/", (req, res) => {
  res.send("123");
});
// 处理上传文件夹的请求
app.post("/upload-folder", upload.array("files"), (req, res) => {
  const files = req.files;
  console.log(files, "files");
  res.send("123");
  //   try {
  //     files.forEach((file) => {
  //       // 这里你可以将文件信息保存到数据库或进行其他处理
  //       console.log(
  //         `Received file: ${file.originalname} with size ${file.size} bytes`
  //       );
  //     });
  //     res.status(200).send("Folder uploaded successfully!");
  //   } catch (error) {
  //     console.error("Error uploading folder:", error);
  //     res.status(500).send("Error uploading folder.");
  //   }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}/`);
});
