def level_alerts(series, rule):
    direction = rule["direction"]
    level = rule["level"]
    alerts = []

    for i in range(1, len(series)):
        prev = series[i - 1][1]
        curr = series[i][1]

        if direction == "below" and prev >= level and curr < level:
            alerts.append(series[i][0])
        elif direction == "above" and prev <= level and curr > level:
            alerts.append(series[i][0])

    return alerts


def ma_cross_alerts(series, rule):
    short_w = rule["short"]
    long_w = rule["long"]
    direction = rule["direction"]

    if len(series) < long_w + 1:
        return []

    closes = [close for _, close in series]

    def sma(i, n):
        return sum(closes[i - n + 1 : i + 1]) / n

    def diff(i):
        # round away float noise so mathematically equal averages compare equal
        return round(sma(i, short_w) - sma(i, long_w), 9)

    alerts = []
    for i in range(long_w, len(series)):
        diff_prev = diff(i - 1)
        diff_curr = diff(i)

        if direction == "above" and diff_prev <= 0 and diff_curr > 0:
            alerts.append(series[i][0])
        elif direction == "below" and diff_prev >= 0 and diff_curr < 0:
            alerts.append(series[i][0])

    return alerts
