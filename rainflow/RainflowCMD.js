const fs = require("fs");
const rainflow = require("./rainflow");

fs.readFile("./TimeSeries.txt", "utf8", (err, data) => {
  if (err) {
    console.error(err);
    return;
  }

  const lines = data.trim().split("\n");
  const stressRange = lines.map((line) => {
    const parts = line.split(/\s+/); // 用正则表达式匹配空白字符
    const value = parseFloat(parts[1]);
    if (isNaN(value)) {
      console.error(`Cannot parse "${parts[1]}" to a float.`);
    }
    return value;
  });

  console.log(stressRange);
  const countCycles = rainflow.countCycles(stressRange, 1e4);

  for (const cycle of countCycles) {
    console.log(cycle);
  }
});
