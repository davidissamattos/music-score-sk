# Tests
List of test commands to run on the CLI that executes most of the functionality

Windows:
```bash
type tests\data\BrahWiMeSample.musicxml | notare show 
type tests\data\BrahWiMeSample.musicxml | notare show --print

type tests\data\MozartPianoSonata.musicxml | notare show 
type tests\data\MozartPianoSonata.musicxml | notare extract --measures "1-3" | notare show 
type tests\data\MozartPianoSonata.musicxml | notare extract --measures "1,3" | notare show 
type tests\data\MozartPianoSonata.musicxml | notare extract --part-number 0 | notare show #show all parts
type tests\data\MozartPianoSonata.musicxml | notare extract --part-number 1 | notare show

type tests\data\MozartPianoSonata.musicxml | notare delete --measures "2-3" | notare show
type tests\data\MozartPianoSonata.musicxml | notare delete --part-number 0 | notare show

type tests\data\MozartPianoSonata.musicxml | notare metadata #all metadata
type tests\data\MozartPianoSonata.musicxml | notare metadata --composer
type tests\data\MozartPianoSonata.musicxml | notare metadata --clef --key-signature --composer --title
type tests\data\c_scale.musicxml | notare set-metadata --composer "J. Doe" | notare metadata --composer

type tests\data\MozartPianoSonata.musicxml | notare analyze



```