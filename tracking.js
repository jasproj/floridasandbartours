/* ============================================
   FloridaSandbarTours — booking_click tracking
   ============================================
   Single source of truth for the booking_click GA4 conversion event.
   Loaded site-wide via <script src="/tracking.js" defer> in <head>.

   Wires every FareHarbor booking anchor via document-level click
   delegation — no per-anchor onclick required. Survives runtime-rendered
   anchors. Firing requires a fareharbor.com href; CSS classes alone never
   fire booking_click (a prior .book-btn / .tour-cta class heuristic could
   record internal navigation as a conversion, and was removed).

   Reads optional data-tour-id / data-tour-name attributes; falls back
   to anchor text content and href when absent.

   Coexistence notes:
   - Anchors with an existing onclick containing "trackBookingClick" are
     skipped so they do not double-fire. One such anchor exists today:
     app.js's rendered tour cards (trackBookingClickEnhanced), which fires
     gtag('booking_click', ...) itself with richer context — it carries the
     operator `company` — than this file's generic fallback provides.
   - The 76 per-page inline a[href*="fareharbor.com"] binders that used to
     hand-roll a second, parameter-poorer booking_click on the same click
     were removed; this delegated handler already covers those anchors and
     additionally catches runtime-rendered ones the binders never saw.

   utm_source tagging:
   - On every FareHarbor link click, we append utm_source=floridasandbartours
     so GA4 can attribute the booking to FST.
   - appendUtmSource is a vendored copy of _tools/generators/source-tag.js
     (_tools PR #84, 4e73885). Inlined here instead of loaded as a
     separate <script> to avoid editing every page <head>.
*/

(function () {
    /* HOSTNAME GUARD — booking_click is emitted from the live domain only.
       ------------------------------------------------------------------
       Measured 2026-08-18 across the network: 84 of 1,066 booking_click
       events came from 127.0.0.1 — local preview servers and Playwright
       runs, not users. This property recorded 0 localhost booking_click to date; the guard is preventive, and 20% of its 90-day sessions were localhost.

       EXACT hostname match, never a heuristic. www 301s to the bare host on
       all nine domains, so location.hostname is always the bare form at
       execution time; the www form is accepted anyway so a future DNS or
       Pages change cannot silently zero conversions.

       Installed as a gtag wrapper rather than a return at each call site
       because this repo emits booking_click from 2 call site(s) across
       2 file(s). Guarding only this file would leave the other emitters
       live and the localhost traffic would simply move to them. Every page
       carrying an inline emitter loads this file, and the inline
       `function gtag()` is defined in <head> before this deferred script
       runs, so the wrapper is installed before any click can fire.

       Only booking_click is suppressed. page_view and every other event are
       passed through untouched, so local QA still renders and reports
       normally — this removes a false conversion, not the tag. */
    var BOOKING_CLICK_ALLOWED_HOSTS = ['floridasandbartours.com', 'www.floridasandbartours.com'];
    function bookingClickHostIsLive() {
        return BOOKING_CLICK_ALLOWED_HOSTS.indexOf(location.hostname) !== -1;
    }
    if (!bookingClickHostIsLive()) {
        var _realGtagForGuard = (typeof window.gtag === 'function') ? window.gtag : null;
        window.gtag = function () {
            if (arguments[0] === 'event' && arguments[1] === 'booking_click') return;
            if (_realGtagForGuard) return _realGtagForGuard.apply(this, arguments);
            (window.dataLayer = window.dataLayer || []).push(arguments);
        };
    }

    function appendUtmSource(url, slug) {
        if (typeof url !== 'string' || !url) return url;
        if (typeof slug !== 'string' || !slug) return url;
        if (url.indexOf('fareharbor.com') === -1) return url;
        if (/[?&]utm_source=/.test(url)) return url;
        var sep = url.indexOf('?') === -1 ? '?' : '&';
        return url + sep + 'utm_source=' + encodeURIComponent(slug);
    }

    function readContext(link) {
        var href = link.getAttribute('href') || '';
        var name = link.dataset.tourName
            || link.textContent.replace(/[→➤➔\s]+$/, '').trim()
            || 'unknown';
        var id = link.dataset.tourId || href || 'unknown';
        return { name: name, id: id, href: href };
    }

    window.trackBookingClick = function (tourName, tourId, region) {
        if (typeof gtag === 'undefined') return;
        gtag('event', 'booking_click', {
            event_category: 'conversion',
            event_label: tourName,
            tour_name: tourName,
            tour_id: tourId,
            region: region || 'florida'
        });
    };

    document.addEventListener('click', function (e) {
        var link = e.target.closest && e.target.closest('a');
        if (!link) return;
        var href = link.getAttribute('href') || '';
        var isFareHarbor = href.indexOf('fareharbor.com') !== -1;
        // The utm_source rewrite runs BEFORE the guard below: it is orthogonal
        // to gtag firing, so tag the destination URL either way.
        if (isFareHarbor) {
            link.href = appendUtmSource(link.href, 'floridasandbartours');
        }
        // The skip-guard sits AFTER the rewrite above, because app.js renders
        // FH anchors with onclick="trackBookingClickEnhanced(...)" and the
        // substring match would otherwise short-circuit the utm_source tagging.
        var onclickAttr = link.getAttribute('onclick') || '';
        if (onclickAttr.indexOf('trackBookingClick') !== -1) return;
        if (!isFareHarbor) return;
        var ctx = readContext(link);
        window.trackBookingClick(ctx.name, ctx.id, 'florida');
    });
})();
