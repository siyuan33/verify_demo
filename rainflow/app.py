from flask import Flask, request, jsonify
import numpy as np

app = Flask(__name__)


def find_turning_points(series):
    turning_points = []
    n = len(series)
    for i in range(1, n - 1):
        if (series[i - 1] < series[i] > series[i + 1]) or (
            series[i - 1] > series[i] < series[i + 1]
        ):
            turning_points.append(series[i])
    return turning_points


def rainflow_count(series):
    turning_points = find_turning_points(series)
    ranges = []
    cycles = []

    stack = []
    for point in turning_points:
        stack.append(point)
        while len(stack) >= 3:
            X = abs(stack[-1] - stack[-2])
            Y = abs(stack[-2] - stack[-3])
            if X >= Y:
                ranges.append(Y)
                cycles.append(0.5)
                stack.pop(-2)
            else:
                break
    for i in range(len(stack) - 1):
        ranges.append(abs(stack[i] - stack[i + 1]))
        cycles.append(0.5)

    return ranges, cycles


@app.route("/rainflow", methods=["POST"])
def rainflow():
    data = request.json
    if "series" not in data:
        return jsonify({"error": "No series provided"}), 400
    series = data["series"]
    ranges, cycles = rainflow_count(series)
    return jsonify({"ranges": ranges, "cycles": cycles})


if __name__ == "__main__":
    app.run(debug=True)
