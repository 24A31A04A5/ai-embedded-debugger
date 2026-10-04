/**
 * sessionStorage protocol for the post-login welcome:
 *   "pending"      — this tab has seen a signed-out state; play on next sign-in.
 *   "play:<epoch>" — playing since <epoch> ms; lets a full-page post-auth
 *                    redirect resume mid-animation instead of restarting.
 * The key is removed once the animation finishes, so refreshes never replay it.
 */
export const WELCOME_STORAGE_KEY = "aed:welcome";
export const WELCOME_PENDING = "pending";
export const WELCOME_PLAY_PREFIX = "play:";

/** Must match the `.welcome-overlay` exit timing in globals.css. */
export const WELCOME_TOTAL_MS = 3500;

export const WELCOME_ATTR = "data-welcome";
export const WELCOME_ELAPSED_VAR = "--welcome-elapsed";

/**
 * Runs before first paint so the overlay covers the destination page the
 * instant it loads, instead of waiting for Clerk to hydrate. Signed-in state
 * is read from Clerk's non-sensitive `__client_uat` cookie (0 when signed out).
 */
export const welcomeBootScript = `(function(){try{
var K=${JSON.stringify(WELCOME_STORAGE_KEY)},T=${WELCOME_TOTAL_MS},s=window.sessionStorage,v=s.getItem(K);
if(!v)return;
var signedIn=document.cookie.split("; ").some(function(c){var i=c.indexOf("=");return c.slice(0,i).indexOf("__client_uat")===0&&c.slice(i+1)!=="0"&&c.slice(i+1)!=="";});
if(!signedIn)return;
if(window.matchMedia("(prefers-reduced-motion: reduce)").matches){s.removeItem(K);return;}
var now=Date.now(),start=now;
if(v.indexOf(${JSON.stringify(WELCOME_PLAY_PREFIX)})===0){start=Number(v.slice(${WELCOME_PLAY_PREFIX.length}))||now;}
else if(v===${JSON.stringify(WELCOME_PENDING)}){s.setItem(K,${JSON.stringify(WELCOME_PLAY_PREFIX)}+now);}
else return;
var elapsed=now-start;
if(elapsed<0||elapsed>=T){s.removeItem(K);return;}
var d=document.documentElement;
d.style.setProperty(${JSON.stringify(WELCOME_ELAPSED_VAR)},elapsed+"ms");
d.setAttribute(${JSON.stringify(WELCOME_ATTR)},"play");
}catch(e){}})();`;
