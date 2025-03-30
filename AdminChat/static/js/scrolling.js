// Import config
import { config } from './config.js';

/**
 * Check if user is at the bottom of the event log
 * @returns {boolean} True if at bottom
 */
export function isAtBottom() {
    const eventLog = document.getElementById('event-log');
    if (!eventLog) return true;

    // Consider "at bottom" if within 100px of the bottom
    return (eventLog.scrollHeight - eventLog.scrollTop - eventLog.clientHeight) < 100;
}

/**
 * Check if user is at the top of the event log
 * @returns {boolean} True if at or near top
 */
export function isNearTop() {
    const eventLog = document.getElementById('event-log');
    if (!eventLog) return false;

    // Consider "near top" if within 100px of the top
    return eventLog.scrollTop < 100;
}

/**
 * Set up all scroll-related event listeners
 */
export function setupScrollHandlers() {
    const eventLog = document.getElementById('event-log');
    if (!eventLog) return;

    // Track scroll position for both top and bottom
    let isLoading = false;

    eventLog.addEventListener('scroll', () => {
        // Check bottom position
        config.wasAtBottom = isAtBottom();
        updateScrollIndicator();

        // Check top position for loading more
        if (isNearTop() && !isLoading && config.hasMoreHistory) {
            isLoading = true;
            loadMoreEntries(eventLog).finally(() => {
                isLoading = false;
            });
        }
    });

    // Handle window resize events
    window.addEventListener('resize', () => {
        // Clear previous timer if it exists
        if (config.resizeTimer) {
            clearTimeout(config.resizeTimer);
        }

        // Check if this is a significant layout change
        const currentWidth = window.innerWidth;
        const isBreakpointCrossed =
            (config.initialWidth <= 768 && currentWidth > 768) ||
            (config.initialWidth > 768 && currentWidth <= 768);

        // Set timer to wait for resize to finish
        config.resizeTimer = setTimeout(() => {
            // Save new width
            config.initialWidth = currentWidth;

            // If user was at bottom OR we crossed a breakpoint, scroll to bottom
            if (config.wasAtBottom || isBreakpointCrossed) {
                scrollToBottom();
            }

            // Update scroll indicator visibility
            updateScrollIndicator();
        }, 250); // Delay to let layout settle
    });

    // Create and add scroll button
    createScrollButton();

    // Initial indicator update
    updateScrollIndicator();
}

/**
 * Create the scroll-to-bottom button if it doesn't exist
 */
export function createScrollButton() {
    if (!document.querySelector('.scroll-bottom-btn')) {
        const scrollButton = document.createElement('button');
        scrollButton.className = 'scroll-bottom-btn';
        scrollButton.textContent = 'Go to bottom';
        scrollButton.title = 'Scroll to bottom';
        scrollButton.addEventListener('click', scrollToBottom);

        // Add to the event log panel
        const eventLogPanel = document.querySelector('.event-log-panel');
        if (eventLogPanel) {
            eventLogPanel.appendChild(scrollButton);
        }
    }
}

/**
 * Load more entries when scrolling to the top
 * @param {HTMLElement} eventLog - The event log element
 * @returns {Promise} A promise that resolves when loading is complete
 */
async function loadMoreEntries(eventLog) {
    // Show loading indicator
    const loadingIndicator = createLoadingIndicator();
    eventLog.insertBefore(loadingIndicator, eventLog.firstChild);

    // Remember current scroll height and position
    const scrollHeight = eventLog.scrollHeight;
    const scrollPosition = eventLog.scrollTop;

    try {
        // Call your load more function (you'll need to implement this)
        // This should return true if more entries were loaded, false if no more history
        const result = await config.loadMoreEntriesCallback();

        // Update if we have more history to load
        if (result === false) {
            config.hasMoreHistory = false;
        }

        // After new entries are added, adjust scroll to maintain position
        requestAnimationFrame(() => {
            const newScrollHeight = eventLog.scrollHeight;
            eventLog.scrollTop = scrollPosition + (newScrollHeight - scrollHeight);
        });

        return result;
    } catch (error) {
        console.error('Error loading more entries:', error);
        return false;
    } finally {
        // Remove loading indicator
        if (loadingIndicator.parentNode) {
            loadingIndicator.parentNode.removeChild(loadingIndicator);
        }
    }
}

/**
 * Create a loading indicator element
 * @returns {HTMLElement} The loading indicator element
 */
function createLoadingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'loading-indicator';
    indicator.textContent = 'Loading...';
    return indicator;
}

/**
 * Update the scroll indicator visibility
 */
export function updateScrollIndicator() {
    const eventLog = document.getElementById('event-log');
    const scrollButton = document.querySelector('.scroll-bottom-btn');

    if (eventLog && scrollButton) {
        const atBottom = isAtBottom();
        scrollButton.style.display = atBottom ? 'none' : 'flex';
        config.wasAtBottom = atBottom;
    }
}

/**
 * Scroll to the bottom of the event log
 */
export function scrollToBottom() {
    const eventLog = document.getElementById('event-log');
    if (!eventLog) return;

    // Handle different layouts
    const isMobileView = window.innerWidth <= 768;

    // Use a combination of approaches for reliability
    eventLog.scrollTop = eventLog.scrollHeight;

    // Use requestAnimationFrame for smooth scrolling after layout
    requestAnimationFrame(() => {
        eventLog.scrollTop = eventLog.scrollHeight;

        // If in mobile view, also ensure the container is in view
        if (isMobileView) {
            const eventLogPanel = document.querySelector('.event-log-panel');
            if (eventLogPanel) {
                eventLogPanel.scrollIntoView({ behavior: 'instant', block: 'end' });
            }
        }

        // Mark as being at bottom
        config.wasAtBottom = true;
        updateScrollIndicator();
    });
}

/**
 * Check if we should auto-scroll based on config and current position
 * @returns {boolean} True if we should auto-scroll
 */
export function shouldScrollToBottom() {
    return config.shouldAutoScroll && config.wasAtBottom;
}
