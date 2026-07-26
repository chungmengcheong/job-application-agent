## Note on how authentication and authorization works in this project

This is a brief note to clarify my mental model of how authentication and authorization works in this project.

## Setup

1. the chrome extension has an unique identifier (chrome extension ID oblgighcolckndbinadplmmmebjemido). it's usually assigned by google. but in my case, i put in a key into manifest.json, which then creates a stable ID. 

2. normally i would register the chrome extension in Google Console to get a client ID. however, for some reason my chrome extension ID and client ID isn't binding. so we created a workaround by instead using a a Wb OAuth client + HTTPS redirect as a bounce. (i.e.,making users auth "off" a web app) . 

3. We registered the web callback in Google Console, i.e., by specifying 
   - an authorized redirect at  URI (airecruitingagent.pythonanywhere.com/oauthcb)
   - data scopes
   - test users 

4. Google gives me a web client ID (258289407737-mdh4gleu91oug8f5g8jqkt75f62te9kv.apps.googleusercontent.com). We hardcode the web client ID and bounce back URI into api.ts. This client ID is not a secret and is ok to be committed. 

5. In manifest.json, we specify through "host_permissions" with domains the browserextension is allowed to access. 

## user auths in app

6. When the user tries to login, the chrome extension starts OAuth. login() builds:
   - reponse_type=token id_token
   - scope=openid email profile
   - redirect_uri=https://airecruitingagent.pythonanywhere.com/oauth2cb
   - state (CSRF protection) and nonce (ID token replay protection)

8. User goes through google's standard oauth flow to provide consent, after which Google redirects to my pythonanywhere URI. The bounce script reads the fragment and forwards the browser to https://<chrome-extension-id>.chromiumapp.org/<same fragment>>

9. launchWebAuthFlow() in the chrome extension picks up the redirect, which contains the token in the URL fragment. I parse the access_token and id_token from the URL fragment, and save them in chrome's local storage. from the chrome extension perspective, we now have an authenticated user. 

## user accesses an authorization required feature, e.g., /review

10. If webapp, browser checks "is this cross-origin?" and whether the CORS policy allows it. If browserextension, this is disregarded.  

11. the extension sends Authorization: Bearer <ID_TOKEN>.

12. on a per endpoint basis, the fastAPI app first uses verify_token(), which wraps Google’s verifier, to check signature (RS256), issuer, audience (aud == your Web client_id), expiry, and nonce. if it passes, the user is authenticated. 

13. the fastAPI app then check that the user is authorized through check_authorized_user(), which references ALLOWED_EMAILS and ALLOWED_domains to determine if the authenticated user is allowed. If not allowed, a 403 is returned.
