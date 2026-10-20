Acolad Digital Radar - Story Generator MVP

What does it do?
- Picks at most one new-ish news item from each of the four topics using the existing bot.py RSS sources.
- Uses a single Gemini API call to select/rewrite the news in concise conversational Persian.
- Tries to get the article's own og:image / twitter:image (no stock image).
- With image: fits image inside an open frame without cutting key parts.
- Without suitable image: creates a brand-native text-only variant instead.
- Creates one intro and up to four news slides, each 1080x1920, plus manifest.json.
- PREVIEW ONLY: does not touch sent_news.json and does not publish to Telegram, Instagram or Buffer.

UPLOAD FILES IN GITHUB (branch main):

Repository ROOT (alongside existing bot.py):
- story_data_builder.py
- story_renderer.py
- story_test.py
- requirements.txt

Into folder .github/workflows/:
- story-test.yml

ALREADY EXISTING IN YOUR REPOSITORY:
- assets/templates/intro_story.png
- assets/templates/tech_story.png
- assets/templates/ai_story.png
- assets/templates/marketing_story.png
- assets/templates/social_story.png
- bot.py (existing, leave unchanged)
- GitHub Secret GEMINI_API_KEY (existing, leave unchanged)

RUN IT:
GitHub -> Actions -> Acolad Story Generator Test -> Run workflow.
After a successful run, open the run's summary and find Artifacts:
acolad-story-previews -> Download.
The downloaded ZIP contains 01_intro.png and the stories plus manifest.json.

IMPORTANT:
- The template PNGs already contain the official Acolad branding. logo_acolad.png is
  reserved for future programmatic templates but is not needed in this MVP.
- Avoid copyright/licensing problems before publicly redistributing article photography;
  keep source attribution and review image rights.
- The fallback to the original article title is for PREVIEW only if Gemini fails;
  it may be English and should not be published as final branded Persian content.
