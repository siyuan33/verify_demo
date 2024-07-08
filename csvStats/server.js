const express = require("express");
const XLSX = require("xlsx");
const multer = require("multer");
const path = require("path");
const cors = require("cors");
const moment = require("moment");
const fs = require("fs"); // 引入 fs 模块用于文件操作
const app = express();
const upload = multer({ dest: "uploads/" });
app.use(cors());
app.use(express.static(path.join(__dirname, "public")));
app.use(express.json());
app.post("/upload", upload.single("file"), (req, res) => {
  const file = req.file;
  if (!file) {
    return res.status(400).json({ message: "未上传文件" });
  }

  const filePath = path.join(__dirname, file.path);

  // 读取上传的 Excel 文件
  const workbook = XLSX.readFile(filePath);
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];

  // 将工作表转换为 JSON 对象数组
  const data = XLSX.utils.sheet_to_json(sheet);

  // 假设时间列为 "报警时间"，找到时间列中的最早时间和最晚时间
  let earliestTime = moment(data[0]["报警时间"], "YYYY-MM-DD");
  let latestTime = moment(data[0]["报警时间"], "YYYY-MM-DD");

  data.forEach((row) => {
    const alarmTime = moment(row["报警时间"], "YYYY-MM-DD");
    if (alarmTime.isBefore(earliestTime)) {
      earliestTime = alarmTime;
    }
    if (alarmTime.isAfter(latestTime)) {
      latestTime = alarmTime;
    }
  });

  // 计算时间跨度（年数）
  const yearsDiff = latestTime.diff(earliestTime, "years");

  // 假设要做一些处理，如统计特定内容的个数等
  let count = 0;
  data.forEach((row) => {
    // 这里可以根据具体的需求进行处理
    if (row["SRM2 SEM1 P3 供电输出"] === "RS485读取状态故障") {
      count++;
    }
  });

  // 返回统计结果和时间跨度
  res.json({
    message: "文件上传成功",
    rowCount: data.length,
    rs485FaultCount: count,
    timeSpanYears: yearsDiff,
    detection: "RS485读取状态故障",
  });

  // 删除 uploads 目录下的所有文件
  fs.readdir("uploads/", (err, files) => {
    if (err) {
      console.error("无法读取 uploads 目录:", err);
      return;
    }

    files.forEach((file) => {
      const filePath = path.join("uploads/", file);
      fs.unlink(filePath, (err) => {
        if (err) {
          console.error(`无法删除文件 ${filePath}:`, err);
        }
      });
    });
  });
});
app.post("/api/generateExcel", (req, res) => {
  const data = req.body;
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.json_to_sheet(data);
  XLSX.utils.book_append_sheet(wb, ws, "Sheet1");
  const excelBuffer = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });
  res.setHeader("Content-Disposition", 'attachment; filename="data.xlsx"');
  res.setHeader(
    "Content-Type",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  );
  res.send(excelBuffer);
});
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
