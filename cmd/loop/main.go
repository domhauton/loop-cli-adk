// Command loop runs project manifests and builds standalone project CLIs.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"

	"github.com/domhauton/loop-cli-adk/internal/authoring"
	"github.com/domhauton/loop-cli-adk/pkg/cli"
	"github.com/domhauton/loop-cli-adk/pkg/operation"
	"github.com/domhauton/loop-cli-adk/pkg/project"
)

var version = "dev"

func main() { os.Exit(run()) }

func run() int {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	return execute(ctx, os.Args[1:], os.Stdout, os.Stderr)
}

func execute(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 || args[0] == "--help" || args[0] == "help" {
		fmt.Fprintln(stdout, "Loop - build agent-facing project CLIs\n\n  loop init --name myproject --dir ./myproject-cli\n  loop init --mode manifest --name myproject --dir .\n  loop check --manifest project.json\n  loop run --manifest project.json -- describe\n  loop run --manifest project.json -- users list --input '{}'\n  loop build --manifest project.json --output bin/myproject --sdk-dir .\n  loop version")
		return 0
	}
	if args[0] == "version" || args[0] == "--version" {
		fmt.Fprintln(stdout, version)
		return 0
	}
	if args[0] == "init" {
		return initialise(args[1:], stdout, stderr)
	}
	if args[0] != "run" && args[0] != "check" && args[0] != "build" {
		return cli.WriteError(stderr, operation.NewError("usage", "expected init, run, check, build or version", nil))
	}
	flags := flag.NewFlagSet(args[0], flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	manifestPath := flags.String("manifest", "project.json", "project manifest")
	var opts authoring.BuildOptions
	if args[0] == "build" {
		flags.StringVar(&opts.Output, "output", "", "destination executable")
		flags.StringVar(&opts.SDKDir, "sdk-dir", "", "local SDK checkout for development")
		flags.StringVar(&opts.SDKVersion, "sdk-version", "", "released SDK semantic version")
		flags.StringVar(&opts.GOOS, "goos", "", "target OS")
		flags.StringVar(&opts.GOARCH, "goarch", "", "target architecture")
	}
	if err := flags.Parse(args[1:]); err != nil {
		if err == flag.ErrHelp {
			usage := map[string]string{
				"check": "loop check --manifest FILE",
				"run":   "loop run --manifest FILE -- COMMAND [--input JSON]",
				"build": "loop build --manifest FILE --output EXECUTABLE (--sdk-dir CHECKOUT | --sdk-version VERSION)",
			}
			fmt.Fprintln(stdout, usage[args[0]])
			if args[0] == "build" {
				fmt.Fprintln(stdout, "Default scaffold SDK:", authoring.DefaultSDKVersion)
			}
			flags.SetOutput(stdout)
			flags.PrintDefaults()
			return 0
		}
		return cli.WriteError(stderr, operation.NewError("usage", err.Error(), err))
	}
	if args[0] != "run" && flags.NArg() != 0 {
		return cli.WriteError(stderr, operation.NewError("usage", "unexpected positional arguments", nil))
	}
	data, err := authoring.ReadManifest(*manifestPath)
	if err != nil {
		return cli.WriteError(stderr, operation.NewError("invalid_manifest", err.Error(), err))
	}
	p, err := project.New(data, os.Getenv)
	if err != nil {
		return cli.WriteError(stderr, err)
	}
	switch args[0] {
	case "check":
		fmt.Fprintln(stdout, `{"valid":true}`)
		return 0
	case "run":
		return cli.Run(ctx, p, flags.Args(), stdout, stderr)
	case "build":
		if err := authoring.Build(ctx, data, opts); err != nil {
			return cli.WriteError(stderr, operation.NewError("build_failed", err.Error(), err))
		}
		fmt.Fprintln(stdout, `{"built":true}`)
		return 0
	}
	return 1
}

func initialise(args []string, stdout, stderr io.Writer) int {
	flags := flag.NewFlagSet("init", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	var opts authoring.InitOptions
	flags.StringVar(&opts.Mode, "mode", authoring.ModeProject, "project or manifest")
	flags.StringVar(&opts.Directory, "dir", ".", "destination directory")
	flags.StringVar(&opts.Name, "name", "", "project executable name")
	flags.StringVar(&opts.SDKVersion, "sdk-version", "", "pinned SDK semantic version (project mode)")
	if err := flags.Parse(args); err != nil {
		if err == flag.ErrHelp {
			fmt.Fprintln(stdout, "loop init --name NAME [--dir DIRECTORY] [--mode project|manifest] [--sdk-version VERSION]\nProject mode creates a standalone CLI, skills, tests and release workflow. Manifest mode creates project.json and an inspection skill for the installed Loop. Existing files are never overwritten.")
			return 0
		}
		return cli.WriteError(stderr, operation.NewError("usage", err.Error(), err))
	}
	if flags.NArg() != 0 {
		return cli.WriteError(stderr, operation.NewError("usage", "unexpected positional arguments", nil))
	}
	result, err := authoring.Init(opts)
	if err != nil {
		return cli.WriteError(stderr, operation.NewError("configuration", "initialise project: "+err.Error(), err))
	}
	if err := json.NewEncoder(stdout).Encode(result); err != nil {
		return cli.WriteError(stderr, operation.NewError("output", "cannot write scaffold result", err))
	}
	return 0
}
