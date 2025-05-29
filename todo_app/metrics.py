# metrics.py
import os, time
from influxdb_client import InfluxDBClient, Point, WriteOptions
from fastapi import Request

client = InfluxDBClient(
    url   = os.getenv("INFLUX_URL"),
    token = os.getenv("INFLUX_TOKEN"),
    org   = os.getenv("INFLUX_ORG"),
)
write = client.write_api(WriteOptions(batch_size=1000, flush_interval=5000))
bucket = os.getenv("INFLUX_BUCKET")


async def latency_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    latency = (time.perf_counter() - t0) * 1000  # ms

    p = (
        Point("http_request")
        .tag("method", request.method)
        .tag("path",  request.url.path)
        .tag("status", response.status_code)
        .field("latency_ms", latency)
    )
    write.write(bucket=bucket, record=p)
    return response


def inc_counter(name: str, tags: dict | None = None, amount: int = 1):
    pt = Point(name)
    if tags:
        for k, v in tags.items():
            pt.tag(k, v)
    pt.field("count", amount)
    write.write(bucket=bucket, record=pt)
