# Step 1, the tech behind it (a personal learning note)

This explains the technologies in Step 1 and why each one is there, so you understand what the build is actually doing. The order follows how a request really flows through the door we are building.

## The one-line purpose of Step 1
Stand up the auth spine: the three separate doors anything ever enters through, each proven to let the right caller in and reject the rest. Everything below is the machinery of those doors.

## 0. The three doors (this is the spine, read it first)
There is not one universal login. There are three callers, in two trust domains, and each carries its own credential and resolves its own tenant (the owner whose data is in scope). Keeping them separate is the whole point of Day 1.

| Door | Who calls | Credential | How the tenant is found | What gets checked |
| --- | --- | --- | --- | --- |
| Owner / ingestion | the human site owner, logged in | Supabase JWT (a real login) | from the JWT's `app_metadata` | signature, issuer, audience, expiry |
| Visitor / widget | a random visitor on the owner's site, NOT logged in | a public widget key (sits in page source, not a secret) | the key maps to a tenant | key is known, Origin/Referer on the key's allowed-domain list, rate limit, then sanitize to just the query |
| MCP | an external AI system (e.g. a customer's agent or ChatGPT) | an external-caller token (a scoped API key or OAuth token), NOT the owner's JWT | from the token | signature, issuer, audience equal to this server, expiry, reject tokens not issued for this server, no token passthrough |

The mistake the original plan made was using the owner's Supabase JWT as the MCP credential too. That is the "token passthrough / wrong audience" error the MCP security spec explicitly forbids, so it is corrected above.

## 1. JWT, the proof of who you are
When a user logs in, Supabase hands them a JWT (JSON Web Token, a small string in three parts, header.payload.signature, separated by dots). The payload holds claims (facts about the user: their id, which tenant they belong to, when the token expires). The signature is the important part: Supabase signs the token with a key, so anyone with Supabase's matching public key can check that signature and know the token is genuine and was not altered. It is stateless, meaning your server does not have to look anything up in a database to trust it, the signature alone proves it. On every token your server checks three things: the signature (is it real), the issuer (did Supabase actually issue it), and the audience (was it meant for this service). If any of those fail, you reject the request.

## 2. Bearer token, how that proof travels
A caller attaches its token to each request in an HTTP header (a small label-and-value pair sent with a web request), specifically `Authorization: Bearer <token>`. "Bearer" means whoever bears, that is holds, this token is treated as that identity. That is why a bearer token must stay secret. This is how the owner login path and the MCP path each learn who is calling, but note they carry DIFFERENT tokens: the owner login carries the Supabase JWT, the MCP carries an external-caller token. The visitor widget path does not use a bearer token at all, it uses the public widget key plus the Origin check.

## 3. Origin validation, where the request came from
Every request a browser makes carries an Origin header (the website it came from, for example https://sheerluxe.com). Origin validation means checking that header against a list of sites you allow and rejecting anything from a site you do not trust. It is a cheap first gate, run before you even bother checking the token. (This is closely tied to CORS, Cross-Origin Resource Sharing, the browser's rule for which outside sites are allowed to call your server at all.)

## 4. Backend-for-frontend, why secrets never touch the browser
Anything in code that runs in the browser can be read by anyone who opens the page. So you never put secret keys (the model API key, or the Supabase service_role key, which is the powerful admin key) in the browser. The backend-for-frontend pattern means the browser only ever talks to your own server, your server holds the secrets, and your server is the one that talks to the AI and the database. The browser holds only a harmless public key. Step 1 wires this in from the start so a secret can never leak out through the frontend.

## 5. MCP, the standard door for AI tools
MCP (Model Context Protocol, a shared standard for how an AI app talks to outside tools and data). Without a standard, every AI tool and every service would invent its own way to connect, which does not scale. MCP fixes the shape of it: a server exposes "tools" (named capabilities, each with a defined input and output), and a client (an AI app, like Claude Code, or a customer's own AI agent) can discover those tools and call them. Your MCP server will eventually expose things like "answer this question and grade its own honesty." On Day 1 it exposes only a stub tool (a placeholder that does almost nothing) just to prove the connection and the security work.

## 6. Streamable-HTTP, how the MCP server talks
MCP can run over different transports (the underlying way two programs send messages to each other). The old way was stdio (standard input and output, where the client and server run on the same machine and talk through the program's input and output streams, like a local pipe). That only works locally. Streamable-HTTP is the modern transport: the server runs as a normal web service reachable over the internet, and it can stream results back over the HTTP connection. You use Streamable-HTTP because your assistant has to be callable remotely, by clients that are not on your machine.

## 7. FastAPI, the server all of this sits on
FastAPI (a Python framework for building web APIs) is the single backend service that will hold the API, the agent, the document-ingestion worker, and the MCP server. The "typed surface" means every endpoint declares the exact shape of its input and output using Python types (via Pydantic), so the contract is explicit and the computer can check it for you.

## Why all of this is on Day 1
The hardest and riskiest part of the whole build is making the MCP door both real and secure. The security spec for it stacks several separate web-security standards on top of each other, and it is easy to get wrong. A real engineering team spent about two weeks just understanding it, built a full version, then threw it away. If that surprise hit you in the final week, with everything already built on top of it, the whole project would slip. So you prove the secured door works on day one, with a stub tool behind it, before anything depends on it. That is the entire reason it goes first: surface the scary unknown early, while you can still react to it.

## A few things worth ranking honestly

On the widget key, the layers are not equal. Strongest to weakest: the narrow scope (the assistant only ever returns tenant-grounded answers, with capped output, so a stolen key buys very little) and the rate limit are load-bearing; the Origin/Referer allowlist is a deterrent (a non-browser client can fake the header); the key store itself is just plumbing (the key is public). So build the Origin check simply and lean on scope plus rate limit. Do not over-build it.

On the MCP, the minimal-but-correct checklist for the Day-1 Resource Server is: pull the bearer token, validate its signature, issuer, audience (equal to this server) and expiry, reject any token not minted for this server, validate the Origin header (403 when present and not allowed), and never forward the inbound token to anything upstream. The fuller OAuth machinery (a Protected Resource Metadata document, dynamic client registration, PKCE) is written up for later, not built now.

On honesty, keep three modes separate so they never blur: the runtime verdict is fused into `answer` (every answer comes with its verdict, it is never an optional step), a standalone evaluator that grades arbitrary text is a separate optional tool, and the offline DeepEval check is a developer-time CI gate, not a runtime tool.

## What "done" looks like
All three doors stand and are tested: the owner's Supabase JWT is verified on the login routes, the widget gate accepts an allowed key from an allowed domain and refuses the rest, and an external AI client connects to your MCP server over Streamable-HTTP, gets checked for an allowed Origin and a genuine external-caller token, and is allowed to list and call the stub tool. Anything missing the right credential or origin is refused. The core behind all three is still a typed stub. That working, secured spine is the proof that the riskiest piece holds.
