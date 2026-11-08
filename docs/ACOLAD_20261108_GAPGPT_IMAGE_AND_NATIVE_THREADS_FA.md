# آکولاد | اصلاح انتشار نوین‌هاب و رشته‌پیام بله/تلگرام — ۸ نوامبر ۲۰۲۶

## وضعیت مستند زنده
- مخزن اصلی پیش از تغییر: `f4d8cc125a338b2dc429d52d152b90c41990bfa9`
- نسخه محافظت‌شده: `safety/acolad-20261108-before-social-publication-repair`
- آزمایش پیش‌نمایش GPT Image با Secret جاری: Run `42460882676`، خطای `GAPGPT_IMAGE_KEY_PRECONSUME_QUOTA_BLOCKED`
- در پنل GapGPT دو کلید دیده می‌شوند: «هدیه» با اعتبار صفر، «تست» با اعتبار نامحدود. GitHub Secrets خواندنی نیست؛ کلید جاری از نظر هویت هنوز قابل تطبیق قطعی نیست.
- آزمایش native Bot API: Run `42461055113`: تلگرام توکن و دسترسی کانال OK؛ `BALE_BOT_TOKEN` در workflow خالی است.
- نوین‌هاب Instagram id 230527 با `login_required:0` متصل است؛ نوع Creator/Business از GET مشخص نیست.
- پیام تلگرام `47` و گروه بله `3698166` برای روایت ۷ نوامبر قبلاً وجود دارند؛ مجوز ارسال دوباره همان روایت وجود ندارد.

## اصلاحات اعمال‌شده روی شاخه آزمایشی
- `acolad_v4_daily_autopublish.py`: `footer_for('telegram')` و `footer_for('bale')` جدا، @channel بومی هر پلتفرم و بدون Markdown خام.
- `acolad_v4_hourly_publish.py`: استفاده از همان فوترهای بومی، حذف Markdown باقی‌مانده، ارسال نوع `image` همراه `media_ids` برای بله/تلگرام در حالت واقعی، و gate `ACOLAD_REQUIRE_REAL_GPT25_ART=1`. در این حالت هر تصویرسازی صرفاً Pillow یا Stock قطعاً بلاک می‌شود.
- `acolad_native_story_threads.py`: سه پیام: اول `sendPhoto`، دوم و سوم `sendMessage` با `reply_to_message_id` همان پیام اول. فقط با Bot API خود شبکه و رسید معتبر؛ در نوین‌هاب امکان reply عمومی مستند نشده و نباید رشته‌پیام جعلی ساخت.
- `tests/test_acolad_native_story_threads.py` و `tests/test_acolad_social_platform_footers.py`: QA ارسال چندبخشی، جلوگیری از ارسال تکراری و حفظ receipt حتی پس از خطای میانی.

## اصلاح GapGPT و دلیل توقف تصویرسازی
شاخه `feature/acolad-gapgpt-transparent-gptimage-20261107` و PR #24 اصلاح شده‌اند: API خروجی را هم از `data[0].b64_json` و هم طبق مستندات GapGPT از `data[0].url` می‌خواند؛ دریافت HTTPS با redirect محدود و چک آلفای PNG است. آزمون ۸ نوامبر نشان داد کلید جاری از مرحله pre-consume سهمیه عبور نمی‌کند، بنابراین هنوز تصویرسازی واقعی به اتمام نرسیده است.

## گام‌های لازم خارج از دسترسی Github API
۱. **کلید درست GapGPT:** در پنل GapGPT از همان کلید «تست» با اعتبار نامحدود استفاده کنید. کلید را **در هیچ پیام/فایل/لاگ** منتشر نکنید. در `GitHub → Settings → Secrets and variables → Actions → GAPGPT_API_KEY → Update secret` کلید کامل را به‌صورت خصوصی جایگزین کنید.
۲. **رشته‌پیام واقعی بله:** در Bale @BotFather بازو بگیرید و به کانال `@acoladagency` حق انتشار بدهید. توکن را در GitHub Secret `BALE_BOT_TOKEN` بگذارید؛ در Variables می‌توانید `BALE_CHANNEL_ID=@acoladagency` تنظیم کنید. اتصال NovinHub فعلی جایگزین توکن ربات بله برای `reply_to_message_id` نیست.

## پیش از انتشار واقعی
- فقط با پژوهش معتبر روز ۸ نوامبر یا روز اجرای جدید؛ روایت روز ۷ نوامبر را برای بار دوم ارسال نکنید.
- حداقل دو منتقد مستقل، منبع دارای تاریخ معتبر، کپشن فارسی سالم، تصویر واقعی `gpt-image-2.5-*` با PNG شفاف و montaj `1080×1920`.
- پس از `PREVIEW PASSED` و تأیید اتصال اینستاگرام Business در نوین‌هاب: ارسال فقط برای شبکه‌هایی که واقعاً پست همان روز ندارند. تلگرام باید ۳ `message_id` واقعی و بله نیز ۳ شناسه داشته باشد؛ اینستاگرام Story Published در شبکه.
- وضعیت‌های `READY`، `SUBMITTED`، `SCHEDULED` معادل `PUBLISHED` نیستند.

## Rollback
- اگر پس از استقرار مشکلی رخ داد: جریان native threads و flag `ACOLAD_REQUIRE_REAL_GPT25_ART` را غیرفعال کنید و کد را از شاخه `safety/acolad-20261108-before-social-publication-repair` بازگردانید.
- **هرگز** رسیدهای ارسال و فایل‌های intent را حذف نکنید. در شک نسبت به انتشار، قبل از هر retry وضعیت کانال و provider را دستی/GET کنترل کنید.
