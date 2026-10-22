"""Plain, neutral stand-ins for every line Cerlen says.

These are used until a line is written in data/voice.json. They are calm and
short on purpose: no emoji, no exclamation marks.
"""

from __future__ import annotations

DEFAULTS: dict[str, str] = {
    # Greetings and help
    "welcome": "Welcome, {user}. Type /help if you need anything.",
    "help_opening": "These are the commands available.",
    # Profiles (build step 6)
    "profile_intro": "Here is the profile for {user}.",
    "profile_empty": "{user} has not added any details yet.",
    "detail_saved": "That has been saved to your profile.",
    "detail_cleared": "That has been cleared from your profile.",
    "favorite_added": "{title} is now in your favorites. You have {count} of 5.",
    "favorite_exists": "{title} is already in your favorites.",
    "favorite_removed": "{title} has been removed from your favorites.",
    "favorite_missing": "That book is not in your favorites.",
    "favorites_full": "Your favorites are full. Choose a position from 1 to 5 to replace one.",
    "invalid_name": "That contains characters that are not allowed. Use letters, numbers, dots, dashes and underscores.",
    "invalid_genre": "A genre can use letters, numbers, spaces, commas, ampersands, apostrophes, slashes and dashes, up to 40 characters.",
    "invalid_goodreads": "Enter a Goodreads username, or a full link that begins with https://www.goodreads.com/.",
    # Books and shelves
    "tbr_added": "{user} has added {title} to their personal shelf.",
    "tbr_exists": "{title} is already on your shelf.",
    "queue_added": "{title} has been added to the queue. There are {count} books in the queue.",
    "queue_exists": "{title} is already in the queue.",
    "start_not_ready": "Starting a club read is not available yet.",
    "ratings_saved": "The outside ratings have been updated.",
    "invalid_outside_rating": "Outside ratings run from 0 to 5.",
    # Errors and empty states
    "not_admin": "That is restricted to the admins.",
    "book_not_found": "I could not find that book in my records.",
    "error": "Something went wrong. Please try again in a moment.",
}
