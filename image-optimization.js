// ===== IMAGE LAZY LOADING =====
// Add lazy loading to all non-critical images

document.addEventListener('DOMContentLoaded', () => {
    const images = document.querySelectorAll('img:not([loading])');
    
    images.forEach((img, index) => {
        // Don't lazy load hero/logo images (load immediately)
        if (img.classList.contains('logo') || 
            img.classList.contains('hero') || 
            img.classList.contains('badge') ||
            index < 5) { // First 5 images load normally
            img.loading = 'eager';
        } else {
            img.loading = 'lazy';
        }
    });
    
    // Fallback for browsers that don't support native lazy loading
    if (!('loading' in HTMLImageElement.prototype)) {
        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                    obs.unobserve(img);
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            observer.observe(img);
        });
    }
});
