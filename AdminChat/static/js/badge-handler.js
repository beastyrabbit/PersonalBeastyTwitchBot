/**
 * Handles all badge-related functionality for Twitch chat
 * Manages rendering and display of user badges
 */

/**
 * Add badges to a message header element
 * @param {Object} badges - Badge data from Twitch
 * @param {Object} userstate - User state data
 * @param {Element} element - Element to add badges to
 */
export function addBadgesToElement(badges, userstate, element) {
    // Process badges object
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
export function getBadgeUrl(badgeType, version) {
    // Special cases for subscriber badges
    if (badgeType === 'subscriber') {
        // Always use highest quality (3)
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

    // For badges not in our mapping, use the Twitch CDN pattern (always highest quality)
    return `https://static-cdn.jtvnw.net/badges/v1/${badgeType}/${version}/3`;
}

/**
 * Get a human-readable title for a badge
 * @param {string} badgeType - Type of badge
 * @param {string} version - Badge version
 * @returns {string} Human-readable badge title
 */
export function getBadgeTitle(badgeType, version) {
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
