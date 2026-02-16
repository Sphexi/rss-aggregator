import datetime as dt
import logging
import os
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, request, render_template

from .config import load_config
from .aggregator import RssAggregator

APP_START = dt.datetime.now(dt.timezone.utc)


def create_app():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config_path = os.getenv("CONFIG_PATH", "/app/config/config.json")
    feed_title = os.getenv("AGG_FEED_TITLE", "Aggregated RSS Feed")
    feed_desc = os.getenv("AGG_FEED_DESCRIPTION", "Filtered RSS feed")
    feed_link = os.getenv("AGG_FEED_LINK", "http://localhost/rss")

    cfg = load_config(config_path)
    aggregator = RssAggregator(cfg, user_agent="RSSAggregator/1.0")

    app = Flask(__name__)
    lock = threading.RLock()
    rss_hits = {"count": 0}

    def refresh_job():
        with lock:
            aggregator.refresh()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(refresh_job, "interval", hours=1)
    scheduler.start()

    with lock:
        aggregator.refresh()

    @app.get("/rss")
    def rss():
        with lock:
            rss_hits["count"] += 1
            logging.info(f"/rss hit from {request.remote_addr}")
            xml = aggregator.build_rss_xml(feed_title, feed_desc, feed_link)
        return Response(xml, mimetype="application/rss+xml")

    @app.get("/status")
    def status():
        with lock:
            data = {
                "uptime": dt.datetime.now(dt.timezone.utc) - APP_START,
                "rss_hits": rss_hits["count"],
                "last_refresh": aggregator.last_refresh_message,
                "items": aggregator.current_items,
                "feeds": cfg.feeds,
            }
        return render_template("status.html", **data)

    return app


app = create_app()
