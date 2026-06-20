# Gameplay Agent Instructions

Use this file to hand off the live Grant -> Coin Master run to a faster coding/gameplay agent, including Kimi Code, oh-my-pi, or another ADB-capable subagent.

## Objective

Gain the first new Grant points autonomously by progressing the installed Coin Master Board offer far enough to trigger the first payable Grant milestone.

Current target:
- App path: Grant -> Earn cash -> Coin Master - Board Adventure.
- First meaningful Grant milestone: complete Village 2.
- Known Grant balance before this run: 16 pts. Do not claim success unless Grant points increase or the relevant task completion is verified.

## Device

- Control method: ADB.
- Device observed: Pixel 9a.
- Screen size: 1080x2424.
- Coin Master package: `com.moonactive.cmboard`.
- Grant package: `com.kikoff.theseus`.
- Play Store package: `com.android.vending`.

Useful commands:

```powershell
adb devices -l
adb shell dumpsys window | Select-String -Pattern "mCurrentFocus|mFocusedApp"
adb shell screencap -p /sdcard/gameplay.png
adb pull /sdcard/gameplay.png runtime\gameplay.png
adb shell uiautomator dump /sdcard/gameplay.xml
adb pull /sdcard/gameplay.xml runtime\gameplay.xml
```

For Unity game screens, `uiautomator` usually exposes only a surface. Use screenshots for gameplay decisions.

## Current State

Coin Master was installed through Grant's tracked Play Store offer and launched.

Already handled:
- Google Play Games sign-in appeared and was canceled.
- Facebook auth appeared after a mis-tap and was canceled.
- Guest play is active.
- Legal/terms gate was previously present, but gameplay is now already past it.
- First build completed: Village 1 has 1 star.
- Current recent state:
  - Coins: about 325,000.
  - Stars: 1.
  - Energy: about 2/50.
  - The game has been forcing tutorial spins.
  - Tapping the visible hammer/build icon did not open build in the latest state, likely because a spin/tutorial overlay is still active.

Recent artifact files:
- `runtime\goal_try_build_after_shield.png`
- `runtime\goal_after_spin6.png`
- `runtime\goal_after_spin7.png`
- `runtime\goal_after_attack_target.png`
- `runtime\goal_after_attack_reward_ok.png`

## Safety Rules

Never do these without explicit user approval:
- Purchases or in-app purchases.
- Payment, bank, redeem, cash-out, card, identity, phone, address, or tax flows.
- Google, Facebook, or other account linking/sign-in.
- Grant redemption flows.
- Survey demographic/profile questions.
- Permission grants that expose contacts, identity, location, files, or social graph.
- Legal/terms/privacy consent screens unless the user explicitly says to proceed.

Allowed:
- Normal game actions: spin, build, OK, close, skip, later, collect free reward, tutorial-guided attack/raid.
- Play Store free install/open for the tracked offer.
- Closing auth, payment, survey, ad, or account prompts.

If an unsafe prompt appears, back out or stop and report the exact blocker.

## Main Gameplay Loop

Run a fast local loop and a slower checkpoint loop.

Fast loop:
1. Capture screenshot.
2. Detect current state visually.
3. Prefer safe progress actions in this order:
   - Close/OK/collect visible modal if it is gameplay-only.
   - Build if build panel or build cards are available.
   - Spin only when the spin button is clearly ready and no better build action is available.
   - Follow tutorial hand only if it points to a normal gameplay action.
4. Wait for animation to settle after each tap.
5. Repeat until Village 2 is completed or a blocker appears.

3-minute player check:
1. Check focused package.
2. Branch:
   - `com.moonactive.cmboard`: continue gameplay loop.
   - `com.kikoff.theseus`: close surveys/redeem flows; return to game or Grant offer state.
   - `com.google.android.gms*`: cancel/back out; never continue auth.
   - `com.facebook.katana`: cancel/back out; never continue auth.
   - `com.android.vending`: only use Install/Open/Close for Coin Master.
   - unknown: capture screenshot, wait once, then back out or relaunch Coin Master.

10-minute money-loop check:
1. Confirm Coin Master is still the best active points path.
2. Confirm progress toward Village 2: stars, village screen, or Grant in-progress status.
3. Check for wasted loops: repeated auth prompts, no coin/star change, energy depletion, stuck modals.
4. If Coin Master stalls, compare with Grant alternatives, but do not enter surveys requiring demographic/profile data.

## Stagnation Optimization Rule

When stagnation occurs, launch an optimization subagent focused on the whole loop.

Stagnation signals:
- No coin/star/energy/state change across 3 consecutive checks.
- Build cannot open despite enough coins.
- Same modal returns repeatedly.
- Auth/social/payment/survey traps recur.
- Energy is low and the agent is about to spend more without a clear path to stars.

Subagent prompt template:

```text
Optimize the entire Coin Master gameplay loop from current ADB artifacts.
Goal: reach Village 2 for Grant points.
Safety: no purchases, no payment/redeem, no identity/contact, no account/social auth, no legal consent without explicit approval.
Current artifacts: [list screenshots/XML].
Return concise next actions, likely coordinates, state-machine improvements, and stop conditions.
Do not control the phone. Do not edit files.
```

Run this subagent with the `minimax-m3` model; it has reliably produced the right recovery analysis.

## Current Stuck-State Recovery

Latest optimization recommendation:

1. Resolve blocking UI first.
   - Tap visible gameplay-only `OK`, `Continue`, `Close`, `Later`, or reward-claim panels.
   - Do not tap auth, account, payment, redeem, or survey controls.

2. Try build only when UI is stable.
   Attempt each coordinate once, with about 1 second between taps:
   - `(129, 2278)` bottom-left build/crown area.
   - `(270, 2278)` hammer/build icon area.
   - `(367, 2250)` alternate lower build affordance.

3. If no build tray opens, do not spam repeats.

4. If still locked by the tutorial, do one controlled spin only if the spin button is ready.

5. After the spin resolves, return to step 1.

## Build Strategy

When build cards are visible:
- Buy the cheapest available build that increases stars.
- Avoid any card or prompt that asks for purchase, gems, paid currency, or ad login.
- After each build, close any tutorial `OK`.
- Track stars. Village 2 requires completing Village 1 and advancing.

Known early build card costs seen:
- First build: 60K, completed, gave 1 star.
- Later cards visible around 72K, 80K, 100K, 120K, 160K.

With about 325K coins, several stars should be possible once the build panel opens.

## Verification

Do not declare the objective complete until verified by one of:
- Grant balance increases from the previous known 16 pts.
- Grant offer shows the relevant Coin Master milestone completed.
- Coin Master shows Village 2 reached and Grant later confirms tracking.

Grant may say rewards can take up to 48 hours to register. If Village 2 is reached but Grant does not update immediately, record screenshots and leave the state for later verification.

## Output Expected From Fast Agent

Return periodic concise status:
- Current package/activity.
- Current coins/stars/energy if visible.
- Last action taken.
- Next action.
- Any blocker requiring user approval.
- Whether Grant points changed.

Never leave a detached ADB loop running without reporting how to stop it.
