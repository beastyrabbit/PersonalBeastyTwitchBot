/**
 * Handles all emote-related functionality for Twitch chat
 * Supports Twitch native emotes, BTTV, and 7TV emotes
 */

import { config } from './config.js';

/**
 * Get 7TV emote URL using files array from v3 API
 * Always returns highest available quality
 *
 * @param {Array} files - Files array from 7TV v3 API
 * @param {string} quality - Desired quality (1x, 2x, 3x, 4x)
 * @returns {string} URL to the emote image
 */
export function get7TVEmoteUrl(files, quality) {
    if (!files || !files.length) {
        return null;
    }

    // Set size mapping
    const sizeMapping = {
        '1x': 1,
        '2x': 2,
        '3x': 3,
        '4x': 4
    };

    const desiredSize = sizeMapping[quality] || 3;

    // Find the best matching file
    let bestFile = files[0];

    // Try to find the exact size match first
    for (const file of files) {
        if (file.width === desiredSize * 28 || file.height === desiredSize * 28) {
            bestFile = file;
            break;
        }
    }

    // Construct CDN URL
    return `https://cdn.7tv.app/emote/${bestFile.name}`;
}

/**
 * Parse a message with emotes and render it to the DOM
 * Handles Twitch native emotes and third-party emotes (BTTV, 7TV)
 * Uses base64 encoded image data from server to display emotes
 *
 * @param {Element} container - Element to add message to
 * @param {string} message - Raw message text
 * @param {string} twitchEmotes - Emote data from Twitch (in the format "emoteID:start-end,start-end/emoteID:start-end")
 */
export async function parseAndRenderMessage(container, message, twitchEmotes) {
    if (config.debug) {
        console.log("parseAndRenderMessage called with:", {
            message: message,
            emotes: twitchEmotes,
            emoteType: typeof twitchEmotes
        });
    }

    // If the message is empty, add nothing
    if (!message || message.trim() === '') {
        return;
    }

    // First, process Twitch emotes by sending the data to the backend
    let emotePositions = [];

    // Send Twitch emote data to backend for processing
    if (twitchEmotes && typeof twitchEmotes === 'string' && twitchEmotes.length > 0) {
        try {
            const response = await fetch('/api/twitch-emotes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ twitchEmotes, message })
            });

            if (response.ok) {
                const twitchEmoteData = await response.json();
                if (twitchEmoteData.emotes && twitchEmoteData.emotes.length > 0) {
                    // Add twitch emotes to our positions array
                    emotePositions = emotePositions.concat(twitchEmoteData.emotes);
                }
            }
        } catch (error) {
            console.error("Error processing Twitch emotes:", error);
        }
    }

    // Now process all words for potential emotes or commands
    if (message.includes(' ') || message.includes('!')) {
        try {
            // Get all words in the message
            const words = message.split(/\s+/);

            // Send all words to backend for batch processing
            const response = await fetch('/api/parse-message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ words, message })
            });

            if (response.ok) {
                const parsedData = await response.json();
                if (parsedData.emotes && parsedData.emotes.length > 0) {
                    // Add all found emotes/commands to our positions array
                    emotePositions = emotePositions.concat(parsedData.emotes);
                }
            }
        } catch (error) {
            console.error("Error parsing message for emotes and commands:", error);
        }
    }

    // If no emotes were found, just add the text
    if (emotePositions.length === 0) {
        container.textContent = message;
        return;
    }

    // Sort emotes by start position to process them in order
    emotePositions.sort((a, b) => a.start - b.start);

    if (config.debug) {
        console.log("Found emotes and commands:", emotePositions);
    }

    // Build message with emotes
    let lastPosition = 0;
    const fragment = document.createDocumentFragment();

    emotePositions.forEach(emote => {
        // Add text before the emote
        if (emote.start > lastPosition) {
            const textNode = document.createTextNode(message.substring(lastPosition, emote.start));
            fragment.appendChild(textNode);
        }

        // Add the emote
        const emoteImg = document.createElement('img');
        emoteImg.className = `chat-emote ${emote.type}-emote`;
        if (emote.animated) {
            emoteImg.classList.add('animated-emote');
        }

        // Get emote code/text from message
        const emoteText = message.substring(emote.start, emote.end + 1);

        // Set alt and title
        emoteImg.alt = emoteText;
        emoteImg.title = emoteText;

        // Use base64 encoded image data directly in src
        if (emote.image_data_b64) {
            const mimeType = emote.mime_type || 'image/png';
            emoteImg.src = `data:${mimeType};base64,${emote.image_data_b64}`;
        } else {
            console.warn(`No image data for emote: ${emoteText}`);
            // Fallback - this shouldn't happen with the updated backend
            if (emote.type === 'twitch') {
                emoteImg.src = `https://static-cdn.jtvnw.net/emoticons/v1/${emote.id}/3.0`;
            } else if (emote.type === 'bttv') {
                emoteImg.src = `https://cdn.betterttv.net/emote/${emote.id}/3x`;
            } else if (emote.type === '7tv' || emote.type === '7tv-unlisted') {
                emoteImg.src = `https://cdn.7tv.app/emote/${emote.id}/4x.webp`;
            } else if (emote.type === 'command') {
                emoteImg.src = emote.url || `/static/commands/${emote.id}.png`;
            }
        }

        // Add any extra classes from the backend
        if (emote.extraClasses) {
            emote.extraClasses.forEach(className => {
                emoteImg.classList.add(className);
            });
        }

        // Handle emote load error
        emoteImg.onerror = function() {
            if (config.debug) {
                console.warn(`Failed to load emote image: ${emoteImg.src}`);
            }
            // Replace with the text
            const textNode = document.createTextNode(emoteText);
            if (emoteImg.parentNode) {
                emoteImg.parentNode.replaceChild(textNode, emoteImg);
            }
        };

        fragment.appendChild(emoteImg);

        lastPosition = emote.end + 1;
    });

    // Add any remaining text
    if (lastPosition < message.length) {
        const textNode = document.createTextNode(message.substring(lastPosition));
        fragment.appendChild(textNode);
    }

    container.appendChild(fragment);

    // Check if message contains only emotes for potential styling
    if (emotePositions.length > 0 && message.trim().split(/\s+/).length === emotePositions.length) {
        container.classList.add('emote-only');
    }
}

