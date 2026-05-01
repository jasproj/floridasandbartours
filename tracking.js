/* ============================================
   FloridaSandbarTours — booking_click tracking
   ============================================
   Single source of truth for the booking_click GA4 conversion event.
   Loaded site-wide via <script src="/tracking.js" defer> in <head>.

   Wires every FareHarbor link, .book-btn, and .tour-cta anchor via
   document-level click delegation — no per-anchor onclick required.
   Survives runtime-rendered anchors.

   Reads optional data-tour-id / data-tour-name attributes; falls back
   to anchor text content and href when absent.
*/

(function () {
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
        var cls = link.classList;
        var isBookBtn = cls && (cls.contains('book-btn') || cls.contains('tour-cta'));
        if (!isFareHarbor && !isBookBtn) return;
        var ctx = readContext(link);
        window.trackBookingClick(ctx.name, ctx.id, 'florida');
    });
})();
