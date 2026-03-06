This is how I want the `azalea init` prompt to look:

```
󱗾 Fetching Minecraft versions
 New pack
├─ Name      (My Pack)   › pack
├─ Author                › author
├─ Version   (0.1.0)     › version
└─ License               › license
```

Be careful to do the border thingys (└─, ├─) correctly, so there is always a '└─' at the bottom!:
EXAMPLE:

```
󱗾 Fetching Minecraft versions
 New pack
├─ Name      (My Pack)   › pack
└─ Author                › author
```
After the user submits the last field (license) it should collapse into a summary with log succes:

```
󱗾 Fetching Minecraft versions
 <oneline summary of block, your design>
```

And should continue on with:

```
 Minecraft version:
├─ a) <top>
├─ b) <5>
├─ c) <latest>
├─ d) <minecraft>
└─ e) <versions>
 Enter letter or version: version

```

And should collapse into:

```
...
 Minecraft version: <selected_version>
```


And finally the loader:

```
 Mod loaders:
├─ fabric
├─ quilt
├─ forge
└─ neoforge
 Select loader (default fabric): loader
```
and collapse to

```
...
 Mod loader: <selected_loader>
```


# CURENT BROKEN STATE:

Currently is is not excaltly as it should be because:

> Be careful to do the border thingys (└─, ├─) correctly, so there is always a '└─' at the bottom!

Is not followed in the first prompt! For example when the user is enering the name of the modpack (nothing below) it is still "├─" and not "└─" even though it is the bottom most one at that time.

And the minecraft version and loader selector prompt looks like this

```
 Minecraft version:
  ├─ a. 1.21.11
  ├─ b. 1.21.10
  ├─ c. 1.21.9
  ├─ d. 1.21.8
  ├─ e. 1.21.7
  ├─ f. 1.21.6
  ├─ g. 1.21.5
  ├─ h. 1.21.4
  ├─ i. 1.21.3
  └─ j. 1.21.2
  › Enter letter or version:

```

So the └─ and ├─ are indented (shouldnt be), and the enter letter or version text is not a log info text, it is also indented and with a different icon. Same for the loaders. Also the list is in a. format not a) format.
