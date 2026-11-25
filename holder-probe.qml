// Synthetic frame switch; does not exercise logind, SDDM or DRM master.
import QtQuick

Window {
    id: probe
    width: 640
    height: 480
    visible: true
    Component.onCompleted: showFullScreen()
    title: "Logout holder probe"
    property string variant: Qt.application.arguments[Qt.application.arguments.length - 1]
    property string phase: "desktop"
    color: phase === "desktop" ? "#316fc0"
         : phase === "holder" || phase === "waiting" ? "#bf8030"
         : phase === "greeter" || phase === "done" ? "#30965d"
         : phase === "fallback" || phase === "failed" ? "#aa36a5" : "#000000"

    onFrameSwapped: {
        if (phase === "holder" || phase === "blank") {
            console.warn("PROBE", phase, "frame swapped")
            phase = phase === "holder" ? "waiting" : "waiting-black"
            if (variant !== "stall")
                incoming.start()
        } else if (phase === "greeter" || phase === "fallback") {
            console.warn("PROBE", phase, "frame swapped")
            deadline.stop()
            phase = phase === "greeter" ? "done" : "failed"
            finish.start()
        }
    }

    Timer {
        interval: 500
        running: true
        onTriggered: {
            deadline.start()
            probe.phase = probe.variant === "stock" ? "blank" : "holder"
        }
    }
    Timer {
        id: incoming
        interval: 700
        onTriggered: probe.phase = "greeter"
    }
    Timer {
        id: deadline
        interval: 1500
        onTriggered: probe.phase = "fallback"
    }
    Timer {
        id: finish
        interval: 300
        onTriggered: Qt.exit(probe.phase === "failed" ? 3 : 0)
    }
}
