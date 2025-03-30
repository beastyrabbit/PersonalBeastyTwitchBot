/**
 * Utility functions for the Twitch chat application
 */

/**
 * Generate a consistent color for a username
 * @param {string} username - Username to generate color for
 * @returns {string} Hex color code
 */
export function getRandomColor(username) {
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
 * Fetch nickname for a user from server API
 * @param {string} username - Lowercase username
 * @returns {Promise<string|null>} User's nickname or null
 */
export async function fetchNickname(username) {
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
