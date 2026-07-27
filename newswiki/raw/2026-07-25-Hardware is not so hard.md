---
title: "Hardware is not so hard"
source: "https://chipweinberger.com/articles/20260719-hardware-is-not-so-hard"
author:
published: 2026-07-19
created: 2026-07-25
description: "What Chip Weinberger learned building and selling 2500 Jamcorder MIDI recorders."
---
## What I learned selling 2500 MIDI recorders, part 1: Hardware is not so hard

A [year and a half ago](https://news.ycombinator.com/item?id=42082430), I launched [Jamcorder](https://jamcorder.com/).

![[_resources/2026-07-25-Hardware is not so hard/37f9889d4bccc045865d3f320ae398ec_MD5.png]]

A Jamcorder, in situ.

It marked the completion of two life goals of mine.

First, I finally had the piano recording device I’d always wanted: a fully automated device that captures everything I play, no human-involvement required.

And second, after a career in software, I got to build hardware. It was super fun.

2500 units have already been sold, and counting! [People genuinely love it!](https://jamcorder.myshopify.com/pages/reviews) And it’s able to stand on its own feet as a business. In my eyes, that’s a success.

For my first blog post, I want to reflect on the biggest surprise I encountered creating Jamcorder.

## Hardware is not so hard

![[_resources/2026-07-25-Hardware is not so hard/3e489032144ada8e68942d14e827fea0_MD5.jpg]]

A selection of prototypes, from the first prototype to the first pre-production unit.

Coming from a career in software, I expected building hardware to be the hardest part.

After all, *hardware is hard*. That’s the saying, right?

Electronics design, plastics, manufacturing, fulfilment, component shortages, etc, etc, etc.

I expected these & more to make hardware hard.

But, *it wasn’t*.

![[_resources/2026-07-25-Hardware is not so hard/fa6f6c18c7c8750ada198935ca1e0202_MD5.jpg]]

To refine the process, I hand assembled the first 500 units myself. It took 4 days. Unexpectedly, everything went completely smoothly and I made no changes. Yes, really.

I kept waiting for something to get me by surprise. A scrapped production run (my worst nightmare). Or component sourcing issues, perhaps?

It never happened. (Though Trump’s tariffs were a close call).

The hardest part of building Jamcorder was still, by far, the software -- roughly 200K lines of code spread across the firmware, app, and manufacturing tooling. It took over 3 years and many long nights in a pre-LLM world.

When compared to that, the hardware was undeniably smooth sailing.

For the record, I don’t think I’m special. It’s just that hardware’s reputation for being difficult is, IMO, overstated.

Now, granted, Jamcorder is -- very much intentionally -- a simple device. *I get that*.

![[_resources/2026-07-25-Hardware is not so hard/468f015dd5cd477581dc5049835192d4_MD5.jpg]]

The Jamcorder PCB. 25 unique components. The MIDI connectors are made to order, everything else on the PCB is off-the-shelf.

Assembly is just a single screw, for a single PCB. The injection mold has generous draft, no slides.

I cut low battery detection, ambient light detection, the power-button, even USB-C.

All these things kept Jamcorder simple.

I’m also under no illusion that 2500 units is a lot by most standards.

But you know what? *The hardware side would have been easy regardless.*

Don’t get me wrong. If Jamcorder was 10x more complex, or 100x more scale, that would be a different story (and a very popular product!).

Or if I was trying to compete in the smartwatch market, or the car market, or any number of very established industries with low margins, *good luck*.

But for me the take away still is: “hardware is as hard as you make it”.

If you’re thinking about building a hardware product & have a way to protect your margins, don’t let building hardware scare you.

It’s not as hard as the saying goes.

POSTSCRIPT

I don’t want to end this article without some practical take-aways. So here are my top recommendations for successfully shipping hardware that worked for me at medium scale:

1. Keep your BOM simple. Avoid single-manufacturer components wherever possible.
2. Avoid complex assembly and calibration.
3. Partner with a Chinese assembly house and suppliers. Alibaba is your friend.
4. Aim for at least 70% gross margin or more.
5. Keep your company lean. Scaling hardware is slower.
6. Have a strong anti-counterfeit strategy. Don’t overlook this.
7. Do final Q/A in-house & hold finished inventory locally.
8. Request samples before every production run.
9. Write a step-by-step manufacturing & assembly guide with pictures.
10. Keep your packaging small. A value dense product makes everything easier.
![[_resources/2026-07-25-Hardware is not so hard/3ff0a33fc6ec2cd019af92c19e856a63_MD5.jpg]]

Me dropping off the first 100 units at the post office. A good day!