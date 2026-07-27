---
title: "How To Choose A Subproblem"
source: "https://millicosm.substack.com/p/how-to-choose-a-subproblem"
author:
  - "[[Mike Winer]]"
published: 2026-07-20
created: 2026-07-25
description: "And why the best subproblem is always 'make a picture'"
---
The biggest weakness I’ve noticed in mentoring junior researchers is ‘problem-solving strategy.’ They have a chestful of medals in math olympiads, they aced every class at MIT. But they’ve also never worked on a problem that took more than 10 hours. Now we want them to produce something over the course of 10 weeks, though for all we know, the problem can be done in 10 days, or perhaps more like 10 years.

Promising young researchers struggle to solve 400-hour problems, but if they’d been handed a sequence of 400 1-hour problems they’d be tearing through them. Nobody can be expected to write down a 400-step plan. The thing to learn, then, is how to peel the next 20-hour problem off of a 400-hour problem, and then peel 1-hour problems off of that. These are important strategic decisions, and making them well requires both practice at the skill and data about the specific problem. I can’t get you data about your problem [^1], but I can help you build the skills.

So in order to save you from a monster problem, I created…

![[_resources/2026-07-25-How To Choose A Subproblem/796f0e91a9d280e266d29a205ded7e47_MD5.webp]]

This advice is mostly aimed at fairly junior people doing some sort of theoretical work, like theoretical physics or computer science or AI alignment. Okay, fine, it’s specifically aimed at the people I’m mentoring at work. But the rest of you should be able to get something out of it, even if you don’t recognize every single example.

### How To Find Subproblems

A standard format for a problem is to answer some question about some system. What is the entropy of this black hole? What’s the expected number of 10-cycles in a random regular graph? How can you prevent a powerful AI from escaping the data center? Given this sort of problem, there are three natural ways to make a subproblem:

1. Ask a simpler question
2. Ask about a simpler system
3. Ask what the fuck is even going on

Suppose someone asks you to adapt ARC’s [cumulant propagation](https://www.alignment.org/blog/mechanistic-estimation-for-wide-random-mlps/) algorithm to work for transformers (if that means nothing to you, reader, just know that we want some kind of algorithm to work on some sort of machine learning thing). There are three natural ways you could try to simplify it.

You can **start small**. There are two time-honored ways of finding a good special case. You can take the simplest case you don’t already understand. The cumulant propagation algorithm is complicated; why don’t we forget about all this cumulant stuff and just deal with means? If you’re a string theorist trying to ask a question about scattering, try just the tree-level amplitudes. If you’re trying to prove something can be done in O(N^2) time, first check that there’s a polynomial-time algorithm.

![[_resources/2026-07-25-How To Choose A Subproblem/4da157146581718b3b8ceef76d2174d5_MD5.webp]]

They say the first step is admitting you have a problem…

You could also work on a **toy problem**. The transformer architecture is complicated. Why not focus on a simpler architecture until you understand how the algorithm works there? Then you can build your way back up.

The goal for toy problems is to find the very simplest system which has the thing you actually care about. I spent a lot of time studying the physics of the liquid-glass transition. Window glass is typically made mostly of silicon and oxygen with various impurities thrown in. But studying hypothetical glass-like substances with just one type of atom was simpler, so that’s what I did.

A physicist’s favorite technique to find toy models is taking limits of the original problem. Why not set the width to infinity? Or the depth? Or the number of tokens?[^2]

![[_resources/2026-07-25-How To Choose A Subproblem/226b8eb56837271650b291005cc79e95_MD5.webp]]

So complicated! Why not work on something simpler first?

A final way to approach a problem is **fact-finding**. Learn basic things about cumulant propagation and about transformers. Maybe that means reading other people’s papers. That’s fine! ‘What does this paper say’ is a very important question to be able to answer, even if you can’t always publish your results. Or you might learn less-basic things. What are the asymptotics of the cumulants in a transformer? What is the distribution of weights in a softmax?

One extremely important variant of fact-finding is **fact-processing**. The information already exists, but you need to shape it into something your brain can better understand. Maybe that means translating from the language of math to the language of economics or physics. But, in my experience, the single most important thing you can do to process information is 🚨 **PUT IT IN A PICTURE🚨**. Your brain has a lot more machinery for visual processing than vector calculus. Put that gray matter to work!

![[_resources/2026-07-25-How To Choose A Subproblem/b3ebc23e25cd6d5192660e30703844ce_MD5.webp]]

If you want to understand an idea… make a picture!

These moves can and should be repeated, creating a fractal structure. In fact, if you look up, you’ll see that the problem your advisor handed you was a sub-sub-sub-problem of something much larger like aligning super-intelligent AI or figuring out a Theory of Everything. Much of the day-to-day work I do is fact-finding about special cases of toy models of one particular approach to the main problem of AI alignment. In situations like this, it’s important to maintain a map of how your subproblem fits into the big picture.

### What Makes A Good Subproblem?

When you work on a subproblem, there are three kinds of payoff. You learn scientific information, you get practice, and you obtain strategic information. Each of those things can be valuable.

#### Knowledge Is Power. Does That Mean More Knowledge Is More Power?

A popular standard for valuable information is **actionable** information. If you know that your larger problem-solving strategy will change depending on the answer to a subproblem, that’s a great reason to work on that subproblem. The standard example here is a subproblem that tells you whether an approach is feasible. To go back to our cumulant-propagation-for-transformers model, the algorithm assumes that the tensor of kth-order cumulants has Frobenius norm O(N), independent of k. Is that still true in a transformer? If not, you’re going to need to do some rethinking.

In my experience, while junior researchers underweight the value of getting actionable information early, advice-to-junior-researchers-givers tend to *overweight* it. The statistic people overlook is how *much* information you expect to get. My go-to example of a high-information activity is making a graph. A function can have so many properties: increasing versus decreasing, the asymptotics at large x and small x. Whether it’s continuous, whether it’s positive, whether it’s periodic. Information-theoretically, a yes-no question has at most one bit of information, but a graph can have tons.

![[_resources/2026-07-25-How To Choose A Subproblem/47dc01c3e3d86d84367ea915620e5734_MD5.webp]]

These are all valid Green’s functions in physics. Wouldn’t you like to know which one the system you’re studying has?

I find these high-information strategies rarely seem actionable in advance. Because there’s so much information, there’s likely to be some sort of surprise that will change your plan. But because of the large number of possible surprises, you don’t have a canned decision tree of what exact approach you’ll use for every possible way the question could shake out. Don’t let that discourage you; ‘I think this will tell me something useful, even if I don’t know how I’ll use it’ is a valid opinion.

#### Maybe The Real Treasure Is The Human Capital We Made Along The Way

Once you’ve solved a problem, you’ll be better at solving problems similar to it. What sort of problems do you want to be better at solving? This has both a short-term component (that cumulant-propagation problem would be easier if you were better at manipulating Hermite polynomials) and a long-term component (I’d be more productive in my career if I knew more about cryptography). The first of these pulls towards solving some fairly simple subproblems involving Hermites. In a pinch, you can probably get a problem set from a textbook. The second tends to push towards going down rabbit holes.

If you’re a first-year grad student or a MATS scholar, most of your (quality-weighted) work is still ahead of you, and becoming a better researcher is a major thing you should be thinking about. But you have to be smart about it. Learning a little about a lot is valuable (especially if you think you can retain it). But in my experience, people tend to overestimate the probability that doing a deep dive on some cool topic will help with the problem at hand. I remember very early in my career being convinced- absolutely convinced- that all my problems would go away if I just understood the Sakai-Sugimoto model. Not only did Sakai-Sugimoto not help with the problem at hand, it’s never helped with a single thing since. If you’re going to spend half a day learning something, please consider whether that thing is going to be useful in the future. And if you do go down rabbit holes in search of human capital (which you should!), be honest with yourself and others about what you’re doing.

#### (Slightly) Against Failing

And of course, if you solve (or fail to solve) a subproblem, you get information about how hard it is, and whether your current approach is working. This is valuable information. It’s nice to know early on if your approach is doomed to fail. Jacob Steinhardt has an excellent [post](https://cs.stanford.edu/~jsteinhardt/ResearchasaStochasticDecisionProcess.html) where he quantifies this, arguing you should sort tasks (roughly) by expected failure probability per unit time, since you save time if you fail early.

In the transformers example, you might think it’s going to be straightforward to work out cumulant propagation through layer norms and skip connections, but it might not be possible to do cumulant propagation through the attention mechanism. Since that has the overwhelming majority of the failure probability, you should do that first.

I’m gonna be honest, I think most advice-givers overweight the value of failing early. Jacob’s model assumes that if any one of the subtasks goes wrong, the approach is dead, and all the intermediate work you did was worthless. I call that a quitter attitude! If an approach seems promising, you shouldn’t abandon it at the first sign of adversity. You should try to patch it. If you read about major scientific programs like the Manhattan Project or the discovery of General Relativity, they’re full of insurmountable obstacles being surmounted by dedicated people who believed in the basic idea.

Of course, you’ll be better at patching your approach if you’ve already done some muscle-building and fact-finding problems. And, come to think of it, if you’ve failed early in the process before you did any muscle-building and fact-finding, what does that really tell us? If an approach seems promising, give it time to breathe and grow before you set out to strangle it in the crib.

![[_resources/2026-07-25-How To Choose A Subproblem/35def6051355b97002f0f0f8cca5b198_MD5.webp]]

Spartans would let children die of exposure if they seemed sickly. In today’s essay, I argue that this was Bad, Actually.

And suppose we buy that there are several must-win subtasks in your approach, which can’t possibly be routed around. Where will you be if your project fails halfway through? Will your intermediate work be worthless? Or will the facts you learned, skills you gained, and technical infrastructure you built up be of value for tackling the next subproblem? That’s not a rhetorical question, by the way; it’s something you should think of when picking subproblems, rather than simply failuremaxxing [^3].

Finally, I don’t like how the Steinhardt framework reduces the outcome of a task to a single yes-no failure. You should always be on the lookout for richer signals than that. What techniques came in handy? Which techniques weren’t up to the task, but seemed like they might be useful next time? Was the problem unexpectedly tough, and if so what does that say about your whole approach?

### What Makes a Bad Subproblem?

We’ve talked about what we want out of a subproblem. What are the potential red flags? A problem can be too vague, too hard, too easy, or too useless. Uselessness is fairly straightforward- we already talked about what makes a subproblem useful; uselessness is just the absence of that. Let’s examine the rest of our rogues’ gallery.

#### I Don’t Know What You’re Talking About

If it takes multiple sentences to describe the problem, even to yourself, that’s a major red flag. It probably means the problem isn’t atomic enough- you could find a simpler, easier-to-think-about problem with a shorter description. It might also be a sign that you, personally, don’t have enough context on the problem. Maybe if you knew more background definitions, you could state the problem more concisely.

Far worse than a long problem statement is a vague problem statement. People don’t do well with vague statements. You’ll have trouble knowing if you’re making progress. And if you try to enlist another mind on your project- human or AI- they will cheerfully start helping you with a different project you never intended. Some ambiguity is necessary in life, but you should strive to eliminate it quickly. For instance, ‘get this algorithm to work for a transformer’ is a slightly vague problem statement. Could be worse, but ideally you could break it into more concrete subproblems.

#### This Is Too Hard

You might not know in advance if a problem is too hard for you. There are some weak heuristics, like whether it’s in a field you know a lot about, and whether it reminds you of some other hard problems you’ve encountered. But by far the best gauge of a problem’s difficulty is whether you have a plan of attack.

The cleanest laboratory I’ve found for thinking about plans of attack is doing integrals, because there is a relatively small number of ‘moves’ you practice again and again. If someone hands you something like

![[_resources/2026-07-25-How To Choose A Subproblem/7734fbdeb28970f3747a1857876a2eb8_MD5.webp]]

you might think of moves like ‘integration by parts’ or ‘substitute x=sinh u’ [^4]. If you’re a little more experienced, you’ll know what shape the problem will take after your first move and can plan another move after that. If you’re *very* experienced, you can map out a path to a solution without ever putting pen to paper. I myself can see three paths to victory through clever substitutions, but the path through integration by parts is murky to me.

The best measure of whether you can solve a problem is how complete your best plan is. The second best measure is how many plans you have. The third best measure is how short your plans are (the more steps, the more chances something will go wrong).

Throughout much of grad school, I held the position that if I didn’t immediately see how to solve a problem, it was impossible, and if I did immediately see how to solve it, I was mistaken. This wasn’t as pessimistic as it sounded because I knew that if I saw how to solve it and my first plan failed, well, I could probably make some other method work.

#### That Was Too Easy

Just as a subproblem can be too hard, it can be too easy. If a subproblem is too hard, you’ll spend weeks or months languishing without progress. If it’s too easy, then a day later you’ll be back at the drawing board with hardly any more insight into the larger program. The point of this section is that THOSE FAILURES ARE NOT EQUALLY BAD. If there’s something which has any chance at all of being important and which you think you could learn in 15 minutes, go and do those fifteen minutes of work.

Many times in my career, there’s been some simple question I kept putting off solving. Eventually, after weeks of frustration, I’d get around to checking this boring, trivial fact. And… it wouldn’t matter. Almost always, I just confirmed what I already suspected and wasted (a very small amount of) my time. But every now and then, that simple check will tell me something that could have saved me a month. Going back to the transformers problem, the question of how cumulant tensors scale with N is something you can answer with ten minutes of work and a Claude subscription. I’m pretty sure I know the answer… but am I *that* sure?

Of course, the paradigmatic example of an easy problem, one you probably already know exactly how to do, is… say it with me

![[_resources/2026-07-25-How To Choose A Subproblem/8a11a7afe668ff5426b08d090bab3852_MD5.webp]]

Make a graph of the size of cumulants as a function of N. Make a histogram of preactivations. And of attention scores. What do I expect to do with that? I have no idea, but I know it won’t cost anything except GPU-hours.

### Maybe I Should Just Quit

Sometimes, you chose the wrong subproblem. If it’s too easy, well, do better next week. But if it’s too useless, too ill-posed, or especially too hard, you can be in trouble. At a certain point you have to put the problem down.

It can be hard to maintain objectivity about the scientific value of the problem you’re working on. It’s even harder to be objective about your prospects of success. These rose-colored glasses are often a good thing; you shouldn’t spend a first date thinking about divorce statistics. But at a certain point, you need to turn to that ultimate destroyer of hope: other people. Tell them what you’ve tried, listen to their suggestions about what they would do (one of them might be good!), and get their frank opinion about whether staying the course is a good use of your time.

Ideally this is your advisor’s job. But a lot of people have hangups about admitting weakness in front of their advisor, and any sort of outside perspective is valuable here. The costs of giving up too early versus too late are asymmetric. Give up too early and you forgo some scientific knowledge (but if you’ve been working long enough, you still get the strategic knowledge and human capital). Give up too late, and you might waste months or years of your career. The latter failure mode is common with young people who don’t have any research experience at all, who don’t want their first project to be a failure. Were it not for a fortunate conversation with a random postdoc, a bad problem might have eaten my grad school career [^5]. So make sure you have that fortunate conversation.

[^1]: Unless you currently work at ARC, in which case, howdy!

[^2]: There’s a quip attributed to Viktor Weisskopf that if physicists were asked to derive the universe from the laws of quantum mechanics, they would predict gases by taking the low-density limit and solids by taking the high-density limit, but liquids would take them completely by surprise.

[^3]: The exception that proves the rule here is my day job at the Alignment Research Center. ARC’s current approach does have multiple points of failure, any one of which would be an enormous setback, if not necessarily a deathblow. And our work is out-of-the-way enough that if it fails, much of the muscle-building and most of the intermediate results and infrastructure will be devalued. Not coincidentally, ARC’s big-picture agenda-setting is dominated by Steinhardt-like failure-per-unit-time considerations. But most projects, like landing a man on the moon or writing a good Substack post or most of the subprojects I work on day-to-day at ARC, have a non-Steinhardtian payoff structure.

[^4]: Yes, I thought of hyperbolic trig before I thought of u=x^2+1. Don’t @ me.

[^5]: About four years later, the problem was solved by someone else. Looking back at their solution, it’s technically complicated and aesthetically unsatisfying and I wasn’t even on the right track.