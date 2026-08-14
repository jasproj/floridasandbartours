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

   utm_source tagging:
   - On every FareHarbor link click, we append utm_source=floridasandbartours
     so GA4 can attribute the booking to FST.
   - appendUtmSource is a vendored copy of _tools/generators/source-tag.js
     (_tools PR #84, 4e73885). Inlined here instead of loaded as a
     separate <script> to avoid editing every page <head>.
*/

(function () {
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
        if (!isFareHarbor) return;
        var ctx = readContext(link);
        window.trackBookingClick(ctx.name, ctx.id, 'florida');
    });
})();
