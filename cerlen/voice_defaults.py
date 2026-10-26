"""Cerlen's lines, as written in the "Cerlen: Script Sheet".

Where the sheet has text, it is copied here word for word. Where the sheet
cell is still empty, a plain neutral line stands in (marked "neutral").
Lines in data/voice.json override these.
"""

from __future__ import annotations

DEFAULTS: dict[str, str] = {
    # Greetings and help
    "welcome": "Welcome to the archives, {user}. Adelyne told me of your arrival... if you are to ever require assistance, you can ask me by typing /help",
    "help_opening": "Below are some things that may guide you through our archives.",
    # New reads and the forum post
    "botm_intro": "The next Everpetal Elite read is {title} by {author}. Those looking to join this read will  have until {deadline} to read the {pages} pages within.",
    "other_intro": "Seems Adelyne has had her interest piqued by {title} by {author}... she plans to read the {pages} pages by {deadline}.",
    "join_prompt": "Join us in reading {title}?",
    "forum_welcome": "Here you may discuss {title} by {author}. Remember to mark spoilers if necessary.\n\nPlease try to finish the book by {deadline}.",
    "member_joined": "{user} has joined the {title} read.",
    "member_left": "{user} has left the {title} read.",
    # Reminders
    "reminder_7": "Greetings, {user}, I noticed that you are only {progress} ways through {title}, and you only have {days_left} days left, so I thought to remind you that the end of the reading period approaches.",
    "reminder_3": "Greetings, {user}, I noticed that you are only {progress} ways through {title}, and you only have {days_left} days left, so I thought to remind you that the end of the reading period approaches.",
    "reminder_1": "{user}, are you a procrastinator, or have you just not updated your progress? It says here you are only {progress} way through of {title}... and there is only a meager day left until the end of the reading period.",
    "reminder_due": "{user}... you are still only {progress} way through of {title}? Do you think you will finish today?",
    "reminder_catchup": "There are only {days_left} days left until the end of the reading period for {title}.",
    "deadline_changed": "Adelyne has changed the deadline for {title} to {deadline}.",
    # Finishing a read
    "read_finished": "Looks like {count} people finished {title}. Let's see here...",
    "review_prompt": "What did you think of {title}?",
    "logbook_intro": "Looks like we had {count} entries for {title}.",
    "logbook_empty": "No thoughts at all? I see...",
    "review_thanks": "Thank you, {user}, for leaving your thoughts on {title}.",
    "review_link": "{user} has left their review here: {link}.",
    # Queue and polls
    "poll_opened": "Adelyne has pulled {count} books from the shelves... if you have a preference on which one to read, you have until {deadline} to let it be known.",
    "poll_result": "Looks like {title} will be the next read, with {count} votes.",
    "poll_tie": "Split votes? Well, I pick {title}, then.",
    "random_pick": "Adelyne closed her eyes, casted a spell, and {title} was chosen as the next book.",
    "next_in_line": "Looks like {title} was up next anyway. I'll choose that one for you all.",
    "chosen_by_admin": "Democracy be damned, Adelyne has chosen {title} to be the next book read.",
    "queue_added": "Adelyne has added {title} to the queue. That makes {count} books in the queue.",
    # Progress, reviews and personal reading
    "progress_saved": "{user} has updated their progress of {title} to {progress}.",
    "halfway": "{user} is halfway through {title}.",
    "finished_book": "{user} has finished {title}.",
    "did_not_finish": "{user} has dropped {title}.",
    "started_reading": "{user} has picked up an extra read of {title}.",
    "tbr_added": "{user} has added {title} to their personal shelf.",
    "note_saved": "{user} has added an annotation to {title}.",
    # Errors and empty states
    "not_admin": "{user}. This section is restricted for Adelyne and I only.",
    "book_not_found": "I couldn't seem to find this book in my records.",
    "invalid_rating": "Can you pick a more normal rating? 1-5, with quarter steps allowed.",
    "page_too_high": "The book only has {pages} pages.",
    "no_discussion_channel": "Adelyne, you have to create the discussion board first.",
    "no_reviews_channel": "Adelyne needs to create the review board first. Yell at her, not me.",
    "no_active_reads": "There isn't a book chosen right now.",
    "queue_empty": "The shelf is... empty? That is strange...",
    "error": "The archives seem dark and empty... looks like Cerlen isn't here?",
    # Profiles (the sheet cells are still empty, so these are neutral)
    "profile_intro": "Here is the profile for {user}.",
    "profile_empty": "{user} has not added any details yet.",
    "detail_saved": "That has been saved to your profile.",
    "detail_cleared": "That has been cleared from your profile.",
    "favorite_added": "{title} is now in your favorites. You have {count} of 5.",
    "favorite_removed": "{title} has been removed from your favorites.",
    "favorites_full": "Your favorites are full. Choose a position from 1 to 5 to replace one.",
    "invalid_name": "That contains characters that are not allowed. Use letters, numbers, dots, dashes and underscores.",
    # Not in the sheet (neutral)
    "favorite_exists": "{title} is already in your favorites.",
    "favorite_missing": "That book is not in your favorites.",
    "invalid_genre": "A genre can use letters, numbers, spaces, commas, ampersands, apostrophes, slashes and dashes, up to 40 characters.",
    "invalid_goodreads": "Enter a Goodreads username, or a full link that begins with https://www.goodreads.com/.",
    "tbr_exists": "{title} is already on your shelf.",
    "queue_exists": "{title} is already in the queue.",
    "start_not_ready": "Starting a club read is not available yet.",
    "ratings_saved": "The outside ratings have been updated.",
    "invalid_outside_rating": "Outside ratings run from 0 to 5.",
}
