// GPU video surface for the live window: colour conversion and scaling run on the GPU (Qt RHI).
// capturemax.py pushes the (delayed) frames into videoSink.
import QtQuick
import QtMultimedia

VideoOutput {
    fillMode: VideoOutput.PreserveAspectFit
}
