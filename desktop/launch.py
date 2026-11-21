"""Desktop and subprocess entry points for the bundled original CLI tools."""
import sys

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--run-tool':
        from desktop.tool_runner import main
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        main()
    else:
        from desktop.app import main
        main()
