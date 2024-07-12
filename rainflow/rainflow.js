const fs = require("fs");

function reversals(series) {
  const result = [];
  let xLast = series[0],
    x = series[1];
  let dLast = x - xLast;
  result.push([0, xLast]);

  for (let i = 1; i < series.length; i++) {
    let xNext = series[i];
    if (xNext === x) continue;
    let dNext = xNext - x;
    if (dLast * dNext < 0) {
      result.push([i, x]);
    }
    xLast = x;
    x = xNext;
    dLast = dNext;
  }
  result.push([series.length - 1, x]);
  return result;
}

function extractCycles(series) {
  const points = [];
  const cycles = [];

  function formatOutput(point1, point2, count) {
    const [i1, x1] = point1;
    const [i2, x2] = point2;
    const rng = Math.abs(x1 - x2);
    const mean = 0.5 * (x1 + x2);
    return [rng, mean, count, i1, i2];
  }

  for (const point of reversals(series)) {
    points.push(point);

    while (points.length >= 3) {
      const x1 = points[points.length - 3][1];
      const x2 = points[points.length - 2][1];
      const x3 = points[points.length - 1][1];
      const X = Math.abs(x3 - x2);
      const Y = Math.abs(x2 - x1);

      if (X < Y) {
        break;
      } else if (points.length === 3) {
        cycles.push(formatOutput(points[0], points[1], 0.5));
        points.shift();
      } else {
        cycles.push(
          formatOutput(
            points[points.length - 3],
            points[points.length - 2],
            1.0
          )
        );
        const last = points.pop();
        points.pop();
        points.pop();
        points.push(last);
      }
    }
  }

  while (points.length > 1) {
    cycles.push(formatOutput(points[0], points[1], 0.5));
    points.shift();
  }

  return cycles;
}

function countCycles(series, binsize = null) {
  const counts = {};
  const cycles = extractCycles(series).map(([rng, , count]) => [rng, count]);

  if (binsize !== null) {
    let nmax = 0;
    for (const [rng, count] of cycles) {
      const n = Math.ceil(rng / binsize);
      counts[n * binsize] = (counts[n * binsize] || 0) + count;
      nmax = Math.max(n, nmax);
    }

    for (let i = 1; i < nmax; i++) {
      counts[i * binsize] = counts[i * binsize] || 0;
    }
  } else {
    for (const [rng, count] of cycles) {
      counts[rng] = (counts[rng] || 0) + count;
    }
  }

  return Object.entries(counts).sort((a, b) => a[0] - b[0]);
}
const rainflow = {};
rainflow.countCycles = countCycles;

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
