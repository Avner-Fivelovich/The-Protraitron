# Contributing to CUB

CUB uses GitHub to manage all open-source development, including bug tracking, pull requests, and design discussions. This document details how to get started as a CUB contributor.

## Table of Contents

1. [Contributing Workflow](#contributing-workflow)
   - [Clone the CUB Repository](#clone-the-cub-repository)
   - [Set Up a Fork of CUB](#set-up-a-fork-of-cub)
   - [Set Up Your Environment](#set-up-your-environment)
   - [Create a Development Branch](#create-a-development-branch)
   - [Local Development Loop](#local-development-loop)
   - [Push Development Branch to Your Fork](#push-development-branch-to-your-fork)
   - [Create a Pull Request](#create-a-pull-request)
   - [Address Feedback and Update Pull Request](#address-feedback-and-update-pull-request)
   - [When Your PR Is Approved](#when-your-pr-is-approved)
2. [CMake Options](#cmake-options)
3. [Development Model](#development-model)
   - [Trunk-Based Development](#trunk-based-development)
   - [Repositories](#repositories)
   - [Versioning](#versioning)
   - [Branches and Tags](#branches-and-tags)

---

## Contributing Workflow

An overview of the contribution process:

1. [Clone the CUB repository](#clone-the-cub-repository)
2. [Set up a fork of CUB](#set-up-a-fork-of-cub)
3. [Set up your environment](#set-up-your-environment)
4. [Create a development branch](#create-a-development-branch)
5. [Local development loop](#local-development-loop)
6. [Push development branch to your fork](#push-development-branch-to-your-fork)
7. [Create pull request](#create-a-pull-request)
8. [Address feedback and update pull request](#address-feedback-and-update-pull-request)
9. [When your PR is approved...](#when-your-pr-is-approved)

### Clone the CUB Repository

To get started, clone the main repository to your local computer:

```bash
git clone https://github.com/thrust/cub.git
cd cub
```

### Set Up a Fork of CUB

You'll need a fork of CUB on GitHub to create a pull request. To set up your fork:

1. Create a GitHub account (if needed).
2. Go to [the CUB GitHub page](https://github.com/thrust/cub).
3. Click **Fork** and follow any prompts that appear.

Once your fork is created, set up a new remote repository in your local CUB clone:

```bash
git remote add github-fork git@github.com:<GITHUB_USERNAME>/cub.git
```

### Set Up Your Environment

#### Git Environment

If you haven't already, configure Git with your identity. This information is used to populate authorship information on your Git commits:

```bash
git config --global user.name "John Doe"
git config --global user.email johndoe@example.com
```

#### Configure CMake Builds

CUB uses [CMake](https://www.cmake.org) for its developer build system. To configure, build, and test your checkout of CUB with default settings:

```bash
# Create build directory:
mkdir build
cd build

# Configure -- use one of the following:
cmake ..   # Command-line interface
ccmake ..  # ncurses GUI (Linux only)
cmake-gui  # Graphical UI (set source/build directories in the app)

# Build:
cmake --build . -j <num_jobs>   # Invokes make (or ninja, etc.)

# Run tests and examples:
ctest
```

See [CMake Options](#cmake-options) for details on customizing the build.

### Create a Development Branch

All work should be done in a development branch (also called a "topic branch") and not directly in the `master` branch. This makes it easier to manage multiple in-progress patches at once and provides a descriptive label for your patch as it passes through the review system.

To create a new branch based on the current `master`:

```bash
# Checkout local master branch:
cd /path/to/cub/sources
git checkout master

# Sync local master branch with GitHub:
git pull

# Create a new branch named `my_descriptive_branch_name` based on master:
git checkout -b my_descriptive_branch_name

# Verify that the branch has been created and is currently checked out:
git branch
```

CUB branch names should follow a structured pattern:

- For new features, name the branch `feature/<name>`.
- For bug fixes associated with a GitHub issue, use `bug/github/<bug-description>-<bug-id>`.
  - Internal NVIDIA and GitLab bugs should use `nvidia` or `gitlab` in place of `github`.

### Local Development Loop

#### Edit, Build, Test, Repeat

Once the topic branch is created, you are ready to work on CUB code. Make changes, then build and test them:

```bash
# Implement changes:
cd /path/to/cub/sources
emacs cub/some_file.cuh # Or your preferred editor

# Create / update a unit test for your changes:
emacs tests/some_test.cu

# Check that everything builds and tests pass:
cd /path/to/cub/build/directory
cmake --build . -j <num_jobs> # Or make, ninja, etc.
ctest
```

#### Creating a Commit

Once you're satisfied with your patch, commit your changes:

```bash
# Manually add changed files and create a commit:
cd /path/to/cub
git add cub/some_file.cuh
git add tests/some_test.cu
git commit

# Or, if available, use git-gui to review your changes while staging:
git gui
```

##### Writing a Commit Message

Your commit message communicates the purpose and rationale behind your patch to other developers and populates the initial description of your GitHub pull request.

Follow this standard format when writing commit messages:

```text
First line of commit message is a short summary (<80 char)
<Second line left blank>
Detailed description of change begins on third line. This portion can
span multiple lines; try to manually wrap them at a reasonable length.

Blank lines can be used to separate multiple paragraphs in the description.

If your patch is associated with another pull request or issue in the main
CUB repository, reference it with a `#` symbol (e.g., #1023 for issue 1023).

For issues / pull requests in a different GitHub repository, reference them
using the full syntax (e.g., thrust/thrust#4 for issue 4 in thrust/thrust).

Markdown is recommended for formatting detailed messages, as these will
be rendered on GitHub.
```

### Push Development Branch to Your Fork

Once you have committed your changes to a local development branch, push them to your fork:

```bash
cd /path/to/cub/checkout
git checkout my_descriptive_branch_name # If not already checked out
git push --set-upstream github-fork my_descriptive_branch_name
```

`--set-upstream github-fork` tells Git that future pushes and pulls on this branch should target your `github-fork` remote by default.

### Create a Pull Request

To create a pull request for your freshly pushed branch:

1. Open your GitHub fork in a browser at `https://github.com/<GITHUB_USERNAME>/cub`.
2. A prompt may automatically appear asking you to create a pull request if you recently pushed a branch.
3. If no prompt appears, navigate to **Code** > **Branches** and click **New pull request** for your branch.
4. If you would like a specific developer to review your patch, request them as a reviewer.

The CUB team will review your patch, run NVIDIA's internal CI testing, and provide feedback.

### Address Feedback and Update Pull Request

If reviewers request changes to your patch, use the following process to update the pull request:

```bash
# Make changes:
cd /path/to/cub/sources
git checkout my_descriptive_branch_name
emacs cub/some_file.cuh
emacs tests/some_test.cu

# Build and test:
cd /path/to/cub/build/directory
cmake --build . -j <num_jobs>
ctest

# Amend commit:
cd /path/to/cub/sources
git add cub/some_file.cuh
git add tests/some_test.cu
git commit --amend
# Or:
git gui # Check the "Amend Last Commit" box

# Update the branch on your fork:
git push -f
```

At this point, the pull request will reflect your updated changes.

### When Your PR Is Approved

Once your pull request is approved by the CUB team, no further action is needed from you. The team will handle integration and coordinate changes to `master` with NVIDIA's internal Perforce repository.

---

## CMake Options

A CUB build is configured using CMake options. These may be passed via the command line:

```bash
cmake -D<option_name>=<value> /path/to/cub/sources
```

Or configured interactively using the `ccmake` or `cmake-gui` interfaces.

Available configuration options:

- `CMAKE_BUILD_TYPE={Release, Debug, RelWithDebInfo, MinSizeRel}`
  - Standard CMake build option. Default: `RelWithDebInfo`.
- `CUB_ENABLE_HEADER_TESTING={ON, OFF}`
  - Whether to test compilation of public headers. Default: `ON`.
- `CUB_ENABLE_TESTING={ON, OFF}`
  - Whether to build unit tests. Default: `ON`.
- `CUB_ENABLE_EXAMPLES={ON, OFF}`
  - Whether to build examples. Default: `ON`.
- `CUB_ENABLE_DIALECT_CPPXX={ON, OFF}`
  - Toggle whether a specific C++ dialect will be targeted.
  - Multiple dialects may be targeted in a single build.
  - Possible values of `XX` are `{11, 14, 17}`.
  - Default: only C++14 is enabled.
- `CUB_ENABLE_COMPUTE_XX={ON, OFF}`
  - Controls targeted CUDA architecture(s).
  - Multiple options may be selected when using NVCC as the CUDA compiler.
  - Valid values of `XX` are: `{35, 37, 50, 52, 53, 60, 61, 62, 70, 72, 75, 80}`.
  - Default value depends on `CUB_DISABLE_ARCH_BY_DEFAULT` (enabled by default when `OFF`).
- `CUB_ENABLE_COMPUTE_FUTURE={ON, OFF}`
  - If enabled, CUDA objects will target the most recent virtual architecture in addition to real architectures specified by `CUB_ENABLE_COMPUTE_XX`.
  - Default value depends on `CUB_DISABLE_ARCH_BY_DEFAULT` (enabled by default when `OFF`).
- `CUB_DISABLE_ARCH_BY_DEFAULT={ON, OFF}`
  - When `ON`, all `CUB_ENABLE_COMPUTE_*` options are initially `OFF`.
  - Default: `OFF` (meaning all supported architectures are enabled by default).
- `CUB_ENABLE_TESTS_WITH_RDC={ON, OFF}`
  - Whether to enable Relocatable Device Code (RDC) when building tests. Default: `OFF`.
- `CUB_ENABLE_EXAMPLES_WITH_RDC={ON, OFF}`
  - Whether to enable Relocatable Device Code (RDC) when building examples. Default: `OFF`.

---

## Development Model

The following describes the basic development process that CUB follows. This is a living document that evolves alongside the development process.

CUB is distributed in three ways:

- On GitHub
- In the NVIDIA HPC SDK
- In the CUDA Toolkit

### Trunk-Based Development

CUB uses [trunk-based development](https://trunkbaseddevelopment.com). There is a single long-lived branch called `master`. Engineers may create branches for feature development, which are always merged into `master`. There are no release branches. Releases are produced by taking a snapshot of `master` ("snapping"). Once a release has been snapped from `master`, it will never be changed.

### Repositories

Because CUB is developed both on GitHub and internally at NVIDIA, code resides across three primary locations:

- **Source of Truth**: The [public CUB repository](https://github.com/thrust/cub) (referred to as `github` in this document).
- **Internal GitLab Repository**: An internal GitLab repository (referred to as `gitlab` in this document).
- **Internal Perforce Repository**: An internal Perforce repository (referred to as `perforce` in this document).

### Versioning

CUB maintains its own versioning system for releases, independent of the NVIDIA HPC SDK or CUDA Toolkit versioning schemes.

CUB version numbers follow [Semantic Versioning](https://semver.org/). Releases prior to 1.10.0 largely, but not strictly, adhered to semantic versioning rules.

The version number format is `MMM.mmm.ss-ppp`:

- `CUB_VERSION_MAJOR` / `MMM`: Major version (up to 3 decimal digits). Incremented when the fundamental nature of the library evolves, resulting in widespread interface changes with no guarantee of API, ABI, or semantic compatibility.
- `CUB_VERSION_MINOR` / `mmm`: Minor version (up to 3 decimal digits). Incremented when breaking API, ABI, or semantic changes are made.
- `CUB_VERSION_SUBMINOR` / `ss`: Subminor version (up to 2 decimal digits). Incremented when notable new features, bug fixes, or enhancements that maintain API, ABI, and semantic backwards compatibility are added.
- `CUB_PATCH_NUMBER` / `ppp`: Patch number (up to 3 decimal digits). Incremented for any repository change when no other version component has been incremented.

The `<cub/version.h>` header defines `CUB_*` macros for all version components listed above. Additionally, the `CUB_VERSION` macro is defined as an integer literal containing all version components except for `CUB_PATCH_NUMBER`.

### Branches and Tags

#### Tag Naming Conventions

- `github/nvhpc-X.Y`: Corresponds directly to what was shipped in NVIDIA HPC SDK release X.Y.
- `github/cuda-X.Y`: Corresponds directly to what was shipped in CUDA Toolkit release X.Y.
- `github/A.B.C`: Corresponds directly to CUB release version A.B.C.

#### Branch Naming Conventions

- `github/master`: The Source of Truth development branch for CUB.
- `github/old-master`: Legacy Source of Truth branch prior to public/internal repository unification.
- `github/feature/<name>`: Feature branch for active development.
- `github/bug/<bug-system>/<bug-description>-<bug-id>`: Bug fix branch, where `<bug-system>` is `github` or `nvidia`.
- `gitlab/master`: Mirror of `github/master`.
- `perforce/private`: Mirrored `github/master` along with files required for internal NVIDIA testing systems.

On rare occasions when work cannot be conducted openly (such as developing features for unreleased hardware/products), branches may reside on `gitlab` instead of `github`. By default, all development is conducted openly on `github`.
