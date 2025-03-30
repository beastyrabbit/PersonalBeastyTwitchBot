/**
 * Entry point for the Twitch chat application
 * Imports the main initialization function and sets up the event listener
 */

import { initializeChatOverlay } from './main.js';


// Initialize when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initializeChatOverlay);
document.addEventListener('DOMContentLoaded', setupScrollListeners());