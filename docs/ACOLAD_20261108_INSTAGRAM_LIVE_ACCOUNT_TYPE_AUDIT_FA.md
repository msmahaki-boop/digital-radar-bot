# بررسی مستقیم حساب اینستاگرام آکولاد در نوین‌هاب — ۸ نوامبر ۲۰۲۶

## یافته قطعی از GET زنده
GitHub Actions [42472421081](https://github.com/msmahaki-boop/digital-radar-bot/actions/runs/42472421081) — API `GET /token/v2/account` با حساب متصل نوین‌هاب و بدون هیچ ارسال عمومی موفق شد (HTTP 200).

- حساب آکولاد: `name=acolad.agency`، `id=230527`، `type=Instagram`، `login_required=0`، `can_send_post=1`.
- فیلد `sub_type` مقدار `null` دارد. هیچ فیلد صریح Business یا Creator در `meta` یا `info` ارائه نشده است.
- شمار حساب‌های Instagram قابل مشاهده: ۲، اما فقط **یک حساب با نام acolad.agency** در خروجی موجود است؛ شناسه جایگزین برای آکولاد ثبت نشده است. هیچ ID دیگری نباید جایگزین 230527 شود.
- درخواست واقعی انتشار Story برای همین ID در [42471633011](https://github.com/msmahaki-boop/digital-radar-bot/actions/runs/42471633011) با HTTP 400 و توضیح صریح نوین‌هاب رد شد: «طبق قوانین فیسبوک، امکان انتشار استوری در صفحات کریتور اینستاگرام وجود ندارد».
- `login_required=0` و `can_send_post=1` صرفاً دسترسی اتصال/برخی ارسال‌ها را نشان می‌دهند، نه تأیید Business بودن حساب یا مجاز بودن Story. از این داده‌ها نمی‌توان Business بودن را نتیجه گرفت.

## تفسیر و مانع
در اپ اینستاگرام حساب بنا به اعلام صاحب حساب به Business تبدیل شده، ولی ثبت حساب نوین‌هاب هنوز هنگام Story POST آن را Creator ارزیابی می‌کند. از GET رسمی قابل‌دسترسی، تغییر این رده یا دکمه رفرش/اتصال OAuth وجود ندارد. بنابراین **راه‌حل قطعی از داخل کد GitHub تأییدشدنی نیست** و نباید ساختگی آن را Business اعلام کرد.

طبق [راهنمای رسمی نوین‌هاب](https://novinhub.com/blog/review-account/) اتصال Instagram Business به سرویس‌های ثالث نیازمند اتصال مناسب Facebook/Instagram است. بهترین ادامه، راه‌اندازی مجدد مجوز همان حساب در پنل رسمی NovinHub است. اگر مشکل ادامه پیدا کرد، [تیکت پشتیبانی](https://novinhub.com/contact) شامل نام حساب، ID داخلی 230527، خطای ValidationException HTTP400 و شناسه اجرای GitHub ثبت شود؛ **کلید API یا رمز را هرگز در تیکت عمومی یا GitHub قرار ندهید**.

## وضعیت سه شبکه و حفاظت
- تلگرام: [48](https://t.me/acoladagency/48) تصویر اصلی، [49](https://t.me/acoladagency/49) و [50](https://t.me/acoladagency/50) پاسخ واقعی به 48. هر سه با receipt تأیید شده‌اند؛ هیچ بازانتشاری مجاز نیست.
- بله: گروه 3699385 در NovinHub وضعیت `published` دارد ولی شناسه خارجی بله هنوز در API ارائه نشده؛ ارسال مجدد تا رفع ابهام ممنوع.
- اینستاگرام: `ABSENT` از دید NovinHub؛ Story هنوز منتشر نشده است.
- Workflow فعال `.github/workflows/acolad-nov8-instagram-recovery.yml` برای تاریخ ۲۰۲۶-۱۱-۰۸ و فقط Instagram فعال است؛ پس از تاریخ هدف، اسکریپت خودش `DATE_EXPIRED_NO_REQUEST` گزارش می‌کند. وضعیت هر بار از provider GET خوانده می‌شود و برای ارسال‌های پذیرفته‌شده یا مبهم retry کورکورانه انجام نمی‌شود.

## برگشت به نسخه امن
نسخه پشتیبان `safety/acolad-20261108-before-ig-recovery` نگه داشته شده است؛ تغییرات روی شاخه تشخیصی، جریان ارسال را فعال یا غیرفعال نمی‌کنند.
