# Mini App prediction screen fix

Fixes race condition in `app/miniapp_static/app.js`.

## Problem

`openPrediction(matchId)` called `setTab('predictions')`.
`setTab()` immediately started `loadCurrentTab()` / `loadPredictions()` asynchronously.
Then `openPrediction()` rendered the selected match form, but the pending `loadPredictions()` request could finish later and overwrite the form.
Visually this looked like the prediction form opened and instantly disappeared.

## Fix

Added `activateTab(tab)` that switches the visible tab without loading its default content.
`openPrediction()` now calls `activateTab('predictions')` instead of `setTab('predictions')`.

## Apply

Copy `app/miniapp_static/app.js` into your project with replacement.
No SQL changes are required.
