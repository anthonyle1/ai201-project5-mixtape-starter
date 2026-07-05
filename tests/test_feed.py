"""
tests/test_feed.py — Mixtape

Tests for the "Friends Listening Now" feed logic.
"""

import pytest
from datetime import datetime, timedelta, timezone, time
from app import create_app, db
from models import User, Song, ListeningEvent, friendships
from services.feed_service import get_friends_listening_now


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def friends(app):
    """Create a viewer with one friend and one non-friend, plus a song to listen to."""
    with app.app_context():
        viewer = User(username="viewer", email="viewer@example.com")
        friend = User(username="friend", email="friend@example.com")
        stranger = User(username="stranger", email="stranger@example.com")
        db.session.add_all([viewer, friend, stranger])
        db.session.flush()

        db.session.execute(friendships.insert().values(user_id=viewer.id, friend_id=friend.id))
        db.session.execute(friendships.insert().values(user_id=friend.id, friend_id=viewer.id))

        song = Song(title="Test Song", artist="Test Artist", genre="test", shared_by=viewer.id)
        db.session.add(song)
        db.session.commit()

        yield {"viewer": viewer, "friend": friend, "stranger": stranger, "song": song}


def _listen(user_id, song_id, when):
    event = ListeningEvent(user_id=user_id, song_id=song_id, listened_at=when)
    db.session.add(event)
    db.session.commit()
    return event

def test_listening_now_excludes_listen_from_yesterday(app, friends):
    """
    A friend who listened late yesterday (a different calendar day than
    today, regardless of what time this test runs) should NOT show up as
    listening now. Fails today because RECENT_THRESHOLD is a rolling 24h
    window rather than "today", so a listen from yesterday at 11:59pm is
    still within the window and incorrectly shows as "listening now".
    """
    with app.app_context():
        now = datetime.now(timezone.utc)
        yesterday_date = (now - timedelta(days=1)).date()
        listened_at = datetime.combine(yesterday_date, time(23, 59), tzinfo=timezone.utc)
        _listen(friends["friend"].id, friends["song"].id, listened_at)

        feed = get_friends_listening_now(friends["viewer"].id)
        friend_ids = [entry["friend"]["id"] for entry in feed]
        assert friends["friend"].id not in friend_ids  # Should be excluded, bug includes it


