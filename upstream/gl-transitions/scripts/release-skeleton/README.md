# gl-transitions

> The open collection of GL Transitions.

Browse all transitions on **[gl-transitions.com](https://gl-transitions.com/)**.

This package exposes an Array<Transition> auto-generated from the [GitHub repository](https://github.com/gl-transitions/gl-transitions).

A Transition is an object with the following shape:

```js
{
  name: string,
  author: string,
  license: string,
  glsl: string,
  defaultParams: { [key: string]: mixed },
  paramsTypes: { [key: string]: string },
  createdAt: string,
  updatedAt: string,
}
```

For more information, please check out the [GitHub repository](https://github.com/gl-transitions/gl-transitions).

## Install

**with npm:**

```sh
npm install gl-transitions
# or
yarn add gl-transitions
```

```js
import GLTransitions from "gl-transitions";
```

**dist script:**

```
https://unpkg.com/gl-transitions@1/gl-transitions.js
```

```js
const GLTransitions = window.GLTransitions
```

**vanilla JSON:**

```
https://unpkg.com/gl-transitions@1/gl-transitions.json
```
