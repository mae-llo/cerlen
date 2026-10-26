"""Plain stand-in lines for things that are not in the Script Sheet (confirmations, small errors).

They are used until you write your own in data/voice.json.

Importing this module adds them to the defaults in voice_defaults.py, so they
can be overridden in data/voice.json like any other line.
"""

from __future__ import annotations

from cerlen.voice_defaults import DEFAULTS

EXTRA: dict[str, str] = {
    "setting_saved": "That setting has been saved.",
    "invalid_time": "Enter the time as HH:MM on a 24-hour clock, for example 09:00.",
    "invalid_timezone": "I do not recognise that timezone. Use a name such as America/New_York.",
    "invalid_days": "Enter the reminder days as numbers from 0 to 60, separated by commas, for example 7,3,1,0.",
    "wrong_channel_type": "That channel is not the right kind. Choose a forum channel or a text channel.",
    "no_permission": "I do not have permission to post in {channel}. Please check my channel permissions.",
    "book_lookup_failed": "I could not reach the book databases just now. Please try again shortly.",
    "button_not_yours": "That is not available to you.",
    # Club reads
    "read_started": "{title} is now underway. {link}",
    "read_finish_ack": "{title} has been closed.",
    "already_running": "{title} is already being read.",
    "botm_running": "There is already a Book of the Month running. Finish or cancel it first, or start this one as an Other read.",
    "read_closed": "That read is no longer open.",
    "already_joined": "You are already reading {title}.",
    "join_ack": "You have been added to {title}.",
    "not_in_read": "You are not in that read.",
    "leave_ack": "You have left {title}. Your progress stays on your shelf.",
    "read_cancelled": "The read of {title} has been cancelled.",
    "confirm_cancel": "Cancel the read of {title}? It will not count in any stats.",
    "no_history": "No finished reads yet.",
    "no_deadline": "That read has no deadline, so there is nothing to remind anyone about.",
    "reminders_sent": "Reminded {count} readers.",
    "invalid_date": "I could not read that date. Try 2026-11-14.",
    "future_date": "That date has not happened yet.",
    # Queue and polls
    "not_in_queue": "That book is not in the queue.",
    "poll_open": "A poll is already open. Close it first.",
    "poll_needs_two": "A poll needs at least two books in the queue.",
    "no_open_poll": "There is no poll open right now.",
    "vote_saved": "Your vote for {title} has been recorded.",
    "poll_closed": "That poll has closed.",
    # Progress, reviews, shelves
    "posted_in_discussion": "Posted here: {link}",
    "not_reading": "You are not reading that. Start it with /reading start, or join the club read.",
    "reading_closed": "You have already closed {title}.",
    "need_page_or_percent": "Give either a page or a percent, not both and not neither.",
    "need_pages_for_percent": "I do not know how many pages that book has, so give a page number instead.",
    "review_need_finished": "You can review a book once you have marked it finished with /progress finished.",
    "no_review": "You have no review for that book.",
    "confirm_delete_review": "Delete your review of {title}?",
    "confirm_delete_reading": "Delete your entry for {title} and every note you wrote on it?",
    "confirm_delete_data": "Delete everything Cerlen holds about you, including your reviews and notes? This cannot be undone.",
    "tbr_empty": "{user} has nothing on their shelf.",
    "not_on_tbr": "That book is not on your shelf.",
    "reading_empty": "{user} has no reading entries.",
    "no_note": "I could not find that note among yours.",
    "noted": "Noted.",
    "data_exported": "Here is everything I hold about you.",
    "data_deleted": "Everything I held about you has been deleted.",
    "help_footer": "Commands marked (admin) are restricted to the admins.",
}

DEFAULTS.update({key: value for key, value in EXTRA.items() if key not in DEFAULTS})
