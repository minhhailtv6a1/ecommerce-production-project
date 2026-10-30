---
name: modern-ecommerce-frontend
description: Build or improve modern customer-facing e-commerce experiences in this frontend, including storefront discovery, image search, product presentation, cart and checkout UX, SEO, accessibility, performance, analytics, and commerce reliability. Use for implementation or review of shopping journeys; do not use for backend model training, Pinecone ingestion, database administration, or merchant-admin systems.
---

# Modern E-commerce Frontend

Build trustworthy, fast shopping experiences that use real commerce data and match the repository's actual backend capabilities.

Before changing code, read `../../AGENTS.md`. When API integration is involved, also inspect `../../../backend/README.md`, FastAPI routes and Pydantic schemas. Repository instructions and the user's explicit requirements override this skill.

## Choose the relevant capability

Apply only the sections needed for the request:

- **Storefront and discovery:** home page, navigation, catalog, category pages, search, filters, sorting, recommendations, and merchandising.
- **Visual search:** image upload, preview, classifier suggestions, category selection, similarity results, and recovery states.
- **Product evaluation:** product cards, product detail, gallery, variants, price, availability, delivery information, reviews, and comparison.
- **Cart and checkout:** cart state, promotions, addresses, shipping, payments, order review, confirmation, and failure recovery.
- **Customer retention:** favorites, recently viewed products, account, orders, notifications, and consent-aware personalization.
- **Platform quality:** responsive behavior, accessibility, SEO, structured data, performance, observability, testing, and security.

Do not build every capability for every task. Deliver the smallest complete shopping journey the user requested.

## Establish the commerce contract first

Inventory the real routes, schemas, environment variables, and existing UI before selecting an implementation. Distinguish among:

1. Data implemented and exposed by the backend.
2. Internal backend services that are not public HTTP contracts.
3. Planned features with no contract yet.
4. Explicitly requested prototype data.

Never infer product fields from a screenshot or invent endpoints from desired UI. Keep fixture-backed prototypes isolated from production adapters and visibly documented. A failed production request must not silently fall back to fake products.

Treat prices, inventory, promotion eligibility, shipping quotes, tax, payment status, and order state as server-authoritative. The client may preview calculations for responsiveness but must reconcile with the server before displaying a final commitment.

## Storefront and product discovery

Make product discovery fast for both customers who know what they want and customers who are exploring.

- Keep global search and the project's image-search entry point easy to reach.
- Use shareable URLs for query, canonical category IDs, supported facets, sort, and pagination.
- Render active filters as removable controls and provide a clear-all action without erasing the search query unless requested.
- Preserve filters and scroll position when a customer opens a product and returns to results where the framework supports it reliably.
- Show result count only when supplied or derivable from the API contract.
- Do not implement a sort option unless the backend can honor it or the complete result set is safely available for client sorting.
- Use pagination or incremental loading according to the API. When using infinite loading, retain a reachable footer and provide an accessible manual load action.
- Treat zero results as a successful state. Suggest removing filters, using another category, changing the image, or trying a simpler query.
- Keep sponsored, personalized, or recommended content distinguishable when those concepts exist.

For autocomplete, separate recent queries, category suggestions, and products semantically. Debounce network requests, cancel stale requests, support keyboard navigation, and do not send queries to analytics before the applicable consent and privacy rules are satisfied.

## Visual product search

Use an explicit workflow such as `idle → validating → ready → classifying → choosing-categories → searching → success/error`. Avoid combinations that allow stale results or duplicate submissions.

- Provide drag-and-drop and a conventional file input; neither may be the only path.
- Preview the selected image, allow replace/remove, and revoke object URLs during cleanup.
- Use only public API limits and supported MIME types. Dataset ingestion formats are not automatically upload-contract formats.
- Preserve ranked category suggestions from the backend.
- Treat the highest-confidence category as editable guidance, never as a mandatory filter.
- Allow one or more category IDs and preserve two-character IDs such as `"00"`.
- Keep classifier confidence distinct from vector similarity.
- Abort obsolete uploads/searches so late responses cannot replace newer results.
- Explain empty and error states with a useful next action.
- Do not store uploaded images or filenames in logs, analytics, persistent browser storage, or third-party tools without an explicit requirement and disclosure.

The current backend exposes health publicly but does not yet expose image upload, product search, or catalog REST endpoints. Verify this state again rather than assuming it remains unchanged.

## Product presentation

Help customers evaluate products without fabricating facts.

Product cards should prioritize the real image, title, current price, and an actionable availability state when present. Reserve image space to avoid layout shift. Keep critical information visible without hover and make the whole interaction understandable to keyboard and screen-reader users.

On product detail pages:

- Use a responsive gallery with correct dimensions, thumbnails operable by keyboard, meaningful alt text, and zoom only when useful.
- Preserve variant identity. A color or size selection should map to a real variant ID, not only a label.
- Update price, media, availability, and purchase controls when the selected variant changes if the contract supports those differences.
- Disable purchase actions only with an explanation customers can perceive.
- Show delivery estimates, returns, ratings, and stock messages only from authoritative data.
- Keep long descriptions readable and sanitize any backend-provided rich HTML before rendering.
- Represent unavailable optional data by omitting or gracefully adapting the section, not by inserting fake values.

Use locale-aware formatting only when currency and locale are known. For VND, use `Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" })`. Do not use floating-point arithmetic to calculate monetary totals.

## Cart behavior

Cart design must remain consistent across navigation, refresh, authentication changes, and server reconciliation.

- Identify lines by the server's product/variant identity plus relevant options, not array position.
- Make quantity constraints visible and validate them on both client and server.
- Optimistic add/update/remove is appropriate only when failure can be rolled back clearly.
- Prevent repeated clicks from creating duplicate requests or unintended quantity changes.
- Reconcile price, inventory, promotions, and discontinued variants when the cart is opened and before checkout.
- Distinguish an empty cart from a cart-loading failure.
- Announce cart changes accessibly without moving focus unexpectedly.
- Do not promise cart persistence until the storage/account contract is defined.

If using browser storage for an explicitly approved guest cart, version and validate the stored shape, store no secrets or sensitive data, handle quota/corruption, and let the server reprice every line.

## Checkout and payment safety

Treat checkout as a state machine with recoverable steps rather than a long form with loosely related booleans.

- Preserve entered non-sensitive data after recoverable failures.
- Validate addresses and shipping options against the server contract.
- Request a new authoritative order summary when an address, delivery method, cart line, or promotion changes.
- Present subtotal, discounts, shipping, tax, and total using server-provided values and labels.
- Prevent duplicate order creation with server-supported idempotency and clear pending UI.
- Never collect or proxy raw card details unless the approved payment architecture explicitly requires PCI-scoped handling. Prefer provider-hosted fields or redirects.
- Do not mark an order successful from a client redirect parameter alone; confirm the order/payment status through the authoritative backend.
- Handle declined, cancelled, timed-out, pending, inventory-changed, and price-changed outcomes separately when the provider/API distinguishes them.
- Keep the customer able to retry safely without creating duplicate charges or orders.

Do not implement a fake checkout or confirmation page that can be mistaken for a real transaction. UI-only prototypes must be visibly identified in code and handoff documentation.

## Rendering and state placement

Use Next.js server capabilities for public, cacheable content and narrow client boundaries for browser interaction.

- Keep filters in URL state when customers should share, bookmark, refresh, or navigate back to them.
- Keep temporary upload previews and in-progress local controls in component/feature state.
- Keep remote product data in the framework's server/data cache or the established query layer.
- Introduce global client state only for genuinely cross-route interactive state such as an approved cart design.
- Do not duplicate the same source of truth in URL, component state, and a global store.
- Make cache rules explicit. Public catalog content, personalized recommendations, prices, inventory, carts, and orders have different freshness and privacy requirements.
- Never cache one customer's private data for another customer.

Prefer Server Components unless interactivity or browser APIs require a Client Component. Keep `"use client"` at the smallest practical boundary.

## Responsive commerce UX

Design from small screens upward while supporting efficient desktop browsing.

- Keep primary search, image upload, filter, cart, and purchase actions reachable with touch and keyboard.
- Use a filter drawer on constrained screens only if active filters remain visible and removable after the drawer closes.
- Avoid fixed elements that cover product information or checkout controls.
- Preserve a logical reading and tab order when grid columns change.
- Ensure dialogs, drawers, carousels, menus, and comboboxes manage focus correctly.
- Use touch targets around 44 CSS pixels where practical and never require hover.
- Verify zoom, long Vietnamese labels, large text, narrow screens, and landscape orientation.

Avoid generic marketplace clutter. Use restrained merchandising, clear hierarchy, consistent design tokens, and one dominant action per decision point.

## Accessibility

Target WCAG 2.2 AA for new work.

- Use semantic HTML before ARIA and native controls before custom controls.
- Give inputs persistent labels and associate validation messages programmatically.
- Provide visible focus, logical headings, skip navigation where useful, and keyboard-complete interaction.
- Announce asynchronous search/cart status with appropriately scoped live regions.
- Do not communicate discount, selection, inventory, error, or order status by color alone.
- Use descriptive link/button names and meaningful product-image alt text without keyword stuffing.
- Respect reduced-motion preferences and avoid auto-advancing content that customers cannot pause.
- Test critical flows with keyboard navigation and an automated accessibility check; automation does not replace manual verification.

## Performance and media

Optimize for quick discovery and purchase actions, not decorative effects.

- Protect Core Web Vitals: reserve media dimensions for CLS, prioritize the true LCP image, and keep interaction handlers light for INP.
- Use `next/image` when image origins and dimensions are compatible, with narrowly configured remote sources and accurate responsive `sizes`.
- Avoid loading full-resolution gallery or result images before needed.
- Keep client bundles small by using server rendering, direct imports, and lazy loading for secondary features.
- Measure the impact before adding carousels, personalization SDKs, review widgets, chat, analytics, or animation libraries.
- Use skeletons that match final geometry. Do not show perpetual spinners without timeout/recovery behavior.
- Test slow network, missing images, delayed APIs, and long product titles.

Progressive Web App, offline browsing, push notifications, and background sync are optional product features, not default requirements. Add them only when requested and define the behavior for stale prices, inventory, and checkout while offline.

## SEO and discoverability

Apply SEO only to public indexable pages.

- Generate unique titles, descriptions, canonical URLs, and social metadata from real page data.
- Use stable semantic URLs and intentional redirect/not-found behavior.
- Add Product, Offer, AggregateRating, BreadcrumbList, or other structured data only when every emitted field is backed by visible authoritative data.
- Keep structured price, currency, availability, and rating consistent with rendered content.
- Do not index private account, cart, checkout, internal search-state, or thin/duplicate filter pages by accident.
- Provide sitemap and robots behavior only after canonical routing and deployment origin are known.

Do not create fake reviews, rating counts, offers, stock, or structured data to make search previews richer.

## Analytics, experimentation, and privacy

Define an event only when it supports a concrete product question. Prefer stable semantic events such as search submitted, category filter changed, product viewed, add-to-cart succeeded, checkout step completed, and purchase confirmed.

- Record successful business outcomes separately from clicks that merely attempted them.
- Keep event payloads versioned and free of secrets, raw images, full search-image filenames, payment data, addresses, tokens, and unnecessary personal data.
- Respect consent and regional privacy requirements before initializing optional tracking.
- Keep analytics failures from breaking shopping flows.
- Prevent duplicate purchase events on refresh and navigation.
- For experiments, keep assignment stable, expose the variant in observability, define the primary metric and guardrails, and preserve accessibility across variants.

Do not add trackers, pixels, session replay, or personalization vendors without an explicit requirement.

## Error handling and observability

Use customer-facing errors that explain the effect and next action without exposing stack traces or providers' secrets.

Classify failures where behavior differs: validation, unauthenticated, forbidden, not found, conflict, inventory/price changed, rate limited, transient server failure, network offline, timeout, and unknown.

- Give safe retry actions only to idempotent requests or requests protected against duplication.
- Preserve a correlation/request ID returned by the backend for support, but do not expose sensitive diagnostic context.
- Log technical details server-side or through the approved error service with redaction.
- Use error boundaries for rendering failures and local recovery UI for request failures.
- Treat missing product images and optional fields as expected data conditions when the contract allows them.

## Verification

Test the behavior most likely to cost trust or revenue:

- Search/filter URLs round-trip correctly, including category `"00"`.
- Upload replacement and cancellation cannot show stale results.
- Product cards and details handle schema-approved missing values.
- Variant changes update the correct identity and purchase state.
- Cart optimistic updates roll back and reconcile after failure.
- Checkout cannot create duplicate orders from repeated submission.
- Pending, declined, cancelled, and successful payment outcomes render distinctly.
- Keyboard users can complete the requested journey.
- Mobile layout, slow network, empty data, API errors, and broken media remain usable.
- Metadata and structured data agree with visible authoritative product information.

Run the repository's existing formatting, lint, type-check, unit/component, end-to-end, and production-build commands that are relevant to the change. Inspect material UI changes at mobile and desktop widths. Report actual commands and results, and identify any portion that remains fixture-backed or blocked by a missing API.

## Completion standard

Finish only when the requested journey is coherent end to end, relevant recovery states work, authoritative commerce values remain server-owned, accessibility and responsive behavior are proportionately verified, and the handoff clearly distinguishes real integration from prototype behavior.
