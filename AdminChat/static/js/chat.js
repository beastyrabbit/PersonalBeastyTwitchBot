/**
 * Twitch Chat Overlay
 * - Uses native Twitch badges
 * - Implements Redis caching for API data
 * - Includes placeholder for nickname functionality
 * - Supports BTTV and 7TV emotes (7TV using v3 API)
 */


// Chat appearance configuration
const config = {
    fadeOutDelay: 15000,      // Message fade out time in ms
    maxMessages: 100,         // Maximum messages to keep in DOM
    emoteSize: 1.5,           // Emote size multiplier
    badgeSize: 1.2,           // Badge size multiplier
    messageLimit: 200,        // Character limit for messages
    hideBotMessages: true,    // Hide known bot messages
    botUsernames: ['nightbot', 'streamelements', 'streamlabs'],
    animateMessages: true,    // Enable message animations
    useColoredNames: true,    // Use Twitch colors for usernames
    showTimestamps: false,    // Show message timestamps
    enableNicknames: true,    // Enable custom nicknames
    enableBTTV: true,         // Enable BTTV emotes
    enable7TV: true,          // Enable 7TV emotes
    emoteQuality: '3x',       // Emote quality - 1x, 2x, or 3x
    debug: true               // Enable debug logging
};

/**
 * Initialize the chat overlay
 */
function initializeChatOverlay() {
    console.log("Initializing Twitch Chat Overlay");
    const container = document.getElementById('chat-container');

    // Create a connection to the server for messages
    const eventSource = new EventSource('/stream');

    // Listen for new messages
    eventSource.onmessage = function(event) {
        try {
            const messageData = JSON.parse(event.data);
            if (config.debug) {
                console.log("Received message:", messageData);
            }
            processMessage(messageData, container);
        } catch (e) {
            console.error("Error processing message:", e);
        }
    };

    // Listen for error events
    eventSource.onerror = function(error) {
        console.error("EventSource error:", error);
        setTimeout(() => {
            console.log("Attempting to reconnect...");
            eventSource.close();
            initializeChatOverlay();
        }, 5000);
    };

    // Add CSS to document
    addStyles();
}

/**
 * Process a chat message and add it to the DOM
 * @param {Object} data - Message data from Twitch
 * @param {Element} container - Container element for chat messages
 */
function processMessage(data, container) {
    // Extract message details
    const userstate = data.author;
    const messageText = data.content;
    const badges = userstate.badges || {};
    const username = userstate.display_name || userstate.name;
    const userId = userstate.room_id || userstate.name;
    const color = userstate.color || getRandomColor(username);
    const twitchEmotes = userstate.emotes || "";

    if (config.debug) {
        console.log("Processing message:", {
            username,
            messageText,
            twitchEmotes
        });
    }

    // Skip bot messages if configured
    if (config.hideBotMessages && config.botUsernames.includes(username.toLowerCase())) {
        return;
    }

    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'chat-message';
    messageElement.dataset.username = userstate.name;

    // Create message header (badges + username)
    const headerElement = document.createElement('div');
    headerElement.className = 'chat-header';

    // Add badges
    addBadgesToElement(badges, userstate, headerElement);

    // Add username with color
    const usernameElement = document.createElement('span');
    usernameElement.className = 'chat-username';

    // Fetch nickname if enabled
    if (config.enableNicknames) {
        fetchNickname(username.toLowerCase())
            .then(nickname => {
                if (nickname) {
                    usernameElement.textContent = `${nickname} (${username})`;
                } else {
                    usernameElement.textContent = username;
                }
            })
            .catch(() => {
                usernameElement.textContent = username;
            });
    } else {
        usernameElement.textContent = username;
    }

    if (config.useColoredNames) {
        usernameElement.style.color = color;
    }
    headerElement.appendChild(usernameElement);

    // Add timestamp if enabled
    if (config.showTimestamps) {
        const timestamp = document.createElement('span');
        timestamp.className = 'chat-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();
        headerElement.appendChild(timestamp);
    }

    messageElement.appendChild(headerElement);

    // Process message content (handling emotes)
    const contentElement = document.createElement('div');
    contentElement.className = 'chat-content';

    // Parse and add message content with emotes
    parseAndRenderMessage(contentElement, messageText, twitchEmotes);

    messageElement.appendChild(contentElement);

    // Add animation class if enabled
    if (config.animateMessages) {
        messageElement.classList.add('animate-in');
    }

    // Add message to container
    container.appendChild(messageElement);

    // Scroll to bottom to show new message
    container.scrollTop = container.scrollHeight;

    // Remove old messages if exceeding limit
    cleanupOldMessages(container);

    // Set fade out timer
    if (config.fadeOutDelay > 0) {
        setTimeout(() => {
            messageElement.classList.add('fade-out');
            setTimeout(() => {
                if (messageElement.parentNode) {
                    messageElement.parentNode.removeChild(messageElement);
                }
            }, 1000); // Animation duration
        }, config.fadeOutDelay);
    }
}

/**
 * Add badges to a message header element
 * @param {Object} badges - Badge data from Twitch
 * @param {Object} userstate - User state data
 * @param {Element} element - Element to add badges to
 */
function addBadgesToElement(badges, userstate, element) {
    // Process badges object first
    if (badges && Object.keys(badges).length > 0) {
        Object.entries(badges).forEach(([badgeType, version]) => {
            addBadge(badgeType, version, element);
        });
    }
}

/**
 * Add a single badge to an element
 * @param {string} badgeType - Type of badge
 * @param {string} version - Badge version
 * @param {Element} element - Element to add badge to
 */
function addBadge(badgeType, version, element) {
    const badgeUrl = getBadgeUrl(badgeType, version);
    if (badgeUrl) {
        const badgeImg = document.createElement('img');
        badgeImg.className = 'chat-badge';
        badgeImg.src = badgeUrl;
        badgeImg.alt = badgeType;
        badgeImg.title = getBadgeTitle(badgeType, version);
        element.appendChild(badgeImg);
    }
}

/**
 * Get the URL for a Twitch badge
 * @param {string} badgeType - Type of badge
 * @param {string} version - Badge version
 * @returns {string} URL to badge image
 */
function getBadgeUrl(badgeType, version) {
    // Special cases for subscriber badges
    if (badgeType === 'subscriber') {
        // For subscriber badges, the version often contains subscription length info
        // For simplicity, we'll use a generic subscriber badge for now
        return 'https://static-cdn.jtvnw.net/badges/v1/5d9f2208-5dd8-11e7-8513-2ff4adfae661/3';
    }

    // Handle other badge types
    const badgeUrls = {
        'broadcaster': 'https://static-cdn.jtvnw.net/badges/v1/5527c58c-fb7d-422d-b71b-f309dcb85cc1/3',
        'moderator': 'https://static-cdn.jtvnw.net/badges/v1/3267646d-33f0-4b17-b3df-f923a41db1d0/3',
        'vip': 'https://static-cdn.jtvnw.net/badges/v1/b817aba4-fad8-49e2-b88a-7cc744dfa6ec/3',
        'premium': 'https://static-cdn.jtvnw.net/badges/v1/bbbe0db0-a598-423e-86d0-f9fb98ca1933/3',
        'partner': 'https://static-cdn.jtvnw.net/badges/v1/d12a2e27-16f6-41d0-ab77-b780518f00a3/3',
        'founder': 'https://static-cdn.jtvnw.net/badges/v1/511b78a9-ab37-472f-9569-457753bbe7d3/3',
        'sub-gifter': 'https://static-cdn.jtvnw.net/badges/v1/f1d8486f-eb2e-4553-b44f-4d614617afc1/3',
        'bits': 'https://static-cdn.jtvnw.net/badges/v1/73b5c3fb-24f9-4a82-a852-2f475b59411c/3',
        'twitch-recap-2023': 'https://static-cdn.jtvnw.net/badges/v1/5c58cc8d-4f1e-4445-9b26-894c3388affe/3'
    };

    // Return the badge URL if it exists in our mapping
    if (badgeUrls[badgeType]) {
        return badgeUrls[badgeType];
    }

    // For badges not in our mapping, use the Twitch CDN pattern
    return `https://static-cdn.jtvnw.net/badges/v1/${badgeType}/${version}/3`;
}

/**
 * Get a human-readable title for a badge
 * @param {string} badgeType - Type of badge
 * @param {string} version - Badge version
 * @returns {string} Human-readable badge title
 */
function getBadgeTitle(badgeType, version) {
    // Special cases
    if (badgeType === 'subscriber') {
        // For subscriber, version might indicate months or tier
        if (version === '3003') {
            return 'Subscriber (3 months, Tier 3)';
        } else if (version.length >= 4) {
            const years = parseInt(version.substring(0, version.length - 3)) || 0;
            const months = parseInt(version.substring(version.length - 3)) || 0;
            let title = 'Subscriber';
            if (years > 0) {
                title += ` (${years} year${years !== 1 ? 's' : ''}`;
                if (months > 0) {
                    title += `, ${months} month${months !== 1 ? 's' : ''}`;
                }
                title += ')';
            } else if (months > 0) {
                title += ` (${months} month${months !== 1 ? 's' : ''})`;
            }
            return title;
        }
        return `Subscriber (${version} months)`;
    }

    if (badgeType === 'sub-gifter') {
        return `Sub Gifter (${version})`;
    }

    // General case
    const titles = {
        'broadcaster': 'Broadcaster',
        'moderator': 'Moderator',
        'vip': 'VIP',
        'premium': 'Twitch Prime',
        'partner': 'Verified',
        'founder': 'Founder',
        'bits': `Bits: ${version}`,
        'glhf-pledge': 'GLHF Pledge',
        'twitch-recap-2023': 'Twitch Recap 2023'
    };

    return titles[badgeType] || badgeType.replace(/-/g, ' ');
}

/**
 * Parse a message with emotes and render it to the DOM
 * @param {Element} container - Element to add message to
 * @param {string} message - Raw message text
 * @param {string} twitchEmotes - Emote data from Twitch (in the format "emoteID:start-end,start-end/emoteID:start-end")
 */
async function parseAndRenderMessage(container, message, twitchEmotes) {
    if (config.debug) {
        console.log("Parsing message:", message);
        console.log("Twitch emotes:", twitchEmotes);
    }

    // If the message is empty, add nothing
    if (!message || message.trim() === '') {
        return;
    }

    // First, handle Twitch emotes
    let emotePositions = [];

    // Parse Twitch emotes string
    if (twitchEmotes && typeof twitchEmotes === 'string' && twitchEmotes.length > 0) {
        try {
            // Format: "emoteID:start-end,start-end/emoteID:start-end"
            const emoteParts = twitchEmotes.split('/');

            emoteParts.forEach(emotePart => {
                if (!emotePart || !emotePart.includes(':')) return;

                const [emoteId, positions] = emotePart.split(':');

                if (!positions) return;

                positions.split(',').forEach(position => {
                    if (!position.includes('-')) return;

                    const [start, end] = position.split('-').map(Number);
                    emotePositions.push({
                        id: emoteId,
                        start: start,
                        end: end,
                        type: 'twitch'
                    });
                });
            });
        } catch (error) {
            console.error("Error parsing Twitch emotes:", error);
        }
    }

    // Now handle BTTV and 7TV emotes
    if ((config.enableBTTV || config.enable7TV) && message.includes(' ')) {
        try {
            // Get all words in the message
            const words = message.split(/\s+/);
            let wordPos = 0;

            if (config.debug) {
                console.log("Checking for third-party emotes in words:", words);
            }

            for (let i = 0; i < words.length; i++) {
                const word = words[i];
                // Calculate the position in the original message
                const start = message.indexOf(word, wordPos);
                const end = start + word.length - 1;
                wordPos = end + 1;

                // Check if this word is a BTTV or 7TV emote by querying the server
                if (config.enableBTTV || config.enable7TV) {
                    try {
                        const response = await fetch(`/api/emote/${encodeURIComponent(word)}`);
                        if (response.ok) {
                            const emoteData = await response.json();

                            if (emoteData.found) {
                                emotePositions.push({
                                    id: emoteData.id,
                                    code: word,
                                    start: start,
                                    end: end,
                                    type: emoteData.type,
                                    animated: emoteData.animated,
                                    imageType: emoteData.imageType,
                                    files: emoteData.files
                                });
                            }
                        }
                    } catch (error) {
                        console.error("Error checking emote:", error);
                    }
                }
            }
        } catch (error) {
            console.error("Error parsing third-party emotes:", error);
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
        console.log("Found emotes:", emotePositions);
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

        // Set appropriate URL based on emote type
        switch (emote.type) {
            case 'twitch':
                // Check if it's an emotesv2 format ID
                if (emote.id.startsWith('emotesv2_')) {
                    emoteImg.src = `https://static-cdn.jtvnw.net/emoticons/v2/${emote.id}/default/dark/3.0`;
                } else {
                    emoteImg.src = `https://static-cdn.jtvnw.net/emoticons/v1/${emote.id}/3.0`;
                }
                break;

            case 'bttv':
                // BTTV emote format
                const bttvQuality = config.emoteQuality === '3x' ? '3x' : (config.emoteQuality === '2x' ? '2x' : '1x');
                emoteImg.src = `https://cdn.betterttv.net/emote/${emote.id}/${bttvQuality}`;

                // Set srcset for responsive display
                emoteImg.srcset = `
                    https://cdn.betterttv.net/emote/${emote.id}/1x 1x,
                    https://cdn.betterttv.net/emote/${emote.id}/2x 2x,
                    https://cdn.betterttv.net/emote/${emote.id}/3x 3x
                `;
                break;

            case '7tv':
            case '7tv-unlisted':
                // 7TV v3 API emote format using files array
                if (emote.files && emote.files.length > 0) {
                    const quality = config.emoteQuality === '3x' ? '4x' : (config.emoteQuality === '2x' ? '2x' : '1x');
                    const baseUrl = get7TVEmoteUrl(emote.files, quality);

                    // Set source to best available quality
                    emoteImg.src = baseUrl;

                    // Build srcset for responsive display
                    let srcset = '';
                    for (const size of ['1x', '2x', '4x']) {
                        const url = get7TVEmoteUrl(emote.files, size);
                        if (url) {
                            srcset += `${url} ${size === '4x' ? '3' : size.charAt(0)}x, `;
                        }
                    }
                    emoteImg.srcset = srcset.slice(0, -2); // Remove trailing comma and space
                } else {
                    // Fallback if files array is not available
                    const quality = config.emoteQuality === '3x' ? '4x' : (config.emoteQuality === '2x' ? '2x' : '1x');
                    emoteImg.src = `https://cdn.7tv.app/emote/${emote.id}/${quality}.webp`;

                    emoteImg.srcset = `
                        https://cdn.7tv.app/emote/${emote.id}/1x.webp 1x,
                        https://cdn.7tv.app/emote/${emote.id}/2x.webp 2x,
                        https://cdn.7tv.app/emote/${emote.id}/4x.webp 3x
                    `;
                }
                break;
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

/**
 * Get 7TV emote URL using files array from v3 API
 * @param {Array} files - Files array from 7TV v3 API
 * @param {string} quality - Desired quality (1x, 2x, 3x, 4x)
 * @returns {string} URL to the emote image
 */
function get7TVEmoteUrl(files, quality) {
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
 * Fetch nickname for a user from server API
 * @param {string} username - Lowercase username
 * @returns {Promise<string|null>} User's nickname or null
 */
async function fetchNickname(username) {
    try {
        const response = await fetch(`/api/nickname/${username}`);

        // Handle API errors
        if (!response.ok) {
            if (response.status === 404) {
                return null;
            }
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();

        // Handle no nickname set
        if (!data || !data.nickname) {
            return null;
        }

        return data.nickname;
    } catch (error) {
        console.error(`Error fetching nickname for ${username}:`, error);
        return null;
    }
}

/**
 * Clean up old messages to prevent DOM from growing too large
 * @param {Element} container - Chat container element
 */
function cleanupOldMessages(container) {
    const messages = container.getElementsByClassName('chat-message');

    if (messages.length > config.maxMessages) {
        // Remove oldest messages first
        for (let i = 0; i < messages.length - config.maxMessages; i++) {
            container.removeChild(messages[0]);
        }
    }
}

/**
 * Generate a consistent color for a username
 * @param {string} username - Username to generate color for
 * @returns {string} Hex color code
 */
function getRandomColor(username) {
    // Default Twitch colors
    const colors = [
        "#FF0000", "#0000FF", "#008000", "#B22222", "#FF7F50",
        "#9ACD32", "#FF4500", "#2E8B57", "#DAA520", "#D2691E",
        "#5F9EA0", "#1E90FF", "#FF69B4", "#8A2BE2", "#00FF7F"
    ];

    // Simple hash function for consistent colors
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
        hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }

    // Use hash to pick a color
    return colors[Math.abs(hash) % colors.length];
}

/**
 * Add CSS styles to the document
 */
function addStyles() {
  console.log("Was moved to CSS File")
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', initializeChatOverlay);
