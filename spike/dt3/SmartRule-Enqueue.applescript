-- Smart Rule probe, AppleScript variant (run 5: the JXA variant left no trace).
-- Records the UUIDs it receives and returns at once.
on performSmartRule(theRecords)
	set out to "{\"entry\":\"smartrule-as\",\"count\":" & (count of theRecords) & ",\"uuids\":["
	set sep to ""
	tell application id "com.devon-technologies.think3"
		repeat with r in theRecords
			set out to out & sep & "\"" & (uuid of r) & "\""
			set sep to ","
		end repeat
	end tell
	set out to out & "]}"
	set p to (POSIX path of (path to home folder)) & "dt3agent-spike/smartrule/" & (random number from 100000 to 999999) & "-as.json"
	set f to open for access (POSIX file p) with write permission
	write out to f as «class utf8»
	close access f
end performSmartRule
