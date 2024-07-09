const fs = require("fs");
const csv = require("csv-parser");
const moment = require("moment");

const results = [];
const filePath = "./alarm.csv";

// 读取CSV文件并进行处理
fs.createReadStream(filePath)
  .pipe(csv())
  .on("data", (data) => results.push(data))
  .on("end", () => {
    // 统计"RS485读取状态故障"的个数
    const faultCount = results.reduce((count, row) => {
      if (row["SRM2 SEM1 P3 供电输出"] === "RS485读取状态故障") {
        return count + 1;
      }
      return count;
    }, 0);

    console.log(`"RS485读取状态故障"的个数: ${faultCount}`);

    // 计算"报警时间"的时间跨度
    const alarmTimes = results.map((row) => row["报警时间"]);
    const startTime = moment(alarmTimes[0]);
    const endTime = moment(alarmTimes[alarmTimes.length - 1]);
    const durationYears = endTime.diff(startTime, "years", true);

    console.log(`时间跨度为: ${durationYears.toFixed(2)} 年`);
  });
