#!/usr/bin/python3

import sys
import getopt
import json
import re

def handleOutputIDs(runObj, obj, ws = ""):
    ret = {"ID": obj["OutputIDs"]["unsignedInt"], "str": []}
    if type(obj["OutputIDs"]["unsignedInt"]) == list:
        if len(obj["OutputIDs"]["unsignedInt"]) != len(obj["OutputIndices"]["unsignedByte"]):
            raise Exception("Inconsistent list lengths")
        for i in range(len(obj["OutputIDs"]["unsignedInt"])):
            ret["str"].append(switchElem(runObj, int(obj["OutputIDs"]["unsignedInt"][i]), ws, int(obj["OutputIndices"]["unsignedByte"][i])))
    else:
        ret["str"].append(switchElem(runObj, int(obj["OutputIDs"]["unsignedInt"]), ws, int(obj["OutputIndices"]["unsignedByte"])))
    return ret

def parseSeqEvent(runObj, ID):
    obj = runObj[ID]["obj"]
    ret = {"cond": None, "exec": None, "arg": None}
    cond = obj["OutputLinks"]["OutputLink"][0]
    exec = obj["OutputLinks"]["OutputLink"][1]
    arg = obj["VariableLinks"]["VariableLink"]

    #if obj["ID"] != 0:
    #    raise Exception("Unexpected SeqEvent format")
    if cond["Name"] != "Try" or exec["Name"] != "Execute" or arg["Name"] != "Argument":
        raise Exception("Unexpected SeqEvent format")

    # optional condition
    if "OutputIDs" in cond:
        condition = " == false || ".join(handleOutputIDs(runObj, cond)["str"])
        # TODO: condition can never be equal to "false" because of the assignment above
        # condition can either be an empty string or it can be 
        # "RV1 == false || RV2 == false || RV3"
        # if handleOutputIDs would return the list ["RV1", "RV2", "RV3"]
        if condition == "false":
            raise Exception("Never executed (TODO: skip event entirely)")
        if condition != "true":
            print("\tif ("+condition+" == false) \n\t\treturn;")

    # optional(?) chain of events to execute when the condition (if any) evaluates to true

    if "OutputIDs" in exec:
        statements = handleOutputIDs(runObj, exec, "\t")
        print(";\n".join(statements["str"])+";")

    #if "OutputIndices" in exec:
    #    ret["exec"]["ndx"] = exec["OutputIndices"]["unsignedByte"]  # 0, 1, 2, [0, 0] or [1, 1]

    # argument associated with the event, if any.
    #if "VariableIDs" in arg:
    #    ret["arg"] = {"ID": arg["VariableIDs"]}
    return ret

def setActive(runObj, ID, ndx, what):
    obj = runObj[ID]["obj"]
    bool = {"Activate": "true", "Deactivate": "false"}
    if type(obj["InputLinks"]["InputLink"]) == list:
        return what+"[\""+obj[what+"Name"]+"\"] = "+bool[obj["InputLinks"]["InputLink"][ndx]["Name"]]
    else:
        raise Exception("Not yet implemented")

def getVarLinkID(obj, context):
    varLink = obj["VariableLinks"]["VariableLink"]
    if varLink["Name"] == context:
        return int(varLink["VariableIDs"]["unsignedInt"])

def setRemoteSchedule(runObj, ID, ndx):
    obj = runObj[ID]["obj"]
    varID = getVarLinkID(obj, "Days")
    if varID:
        return "Schedule.insert(date_today.addDays("+switchElem(runObj, varID, "")+"))"
    else:
        raise Exception("Unimplemented timeframe (Name)\n"+str(obj["VariableLinks"]["VariableLink"]))

def SeqVar_Double(runObj, ID, ndx):
    obj = runObj[ID]["obj"]
    if "IsRandom" in obj and obj["IsRandom"]:
        if "Dbl" not in obj:
            raise Exception("Expected double")

        if "MinRandom" in obj:
            return obj["MinRandom"]+" + qrand("+obj["Dbl"]+" - "+obj["MinRandom"]+")"
        else:
            return "qrand("+obj["Dbl"]+")"
    else:
        raise Exception("Not yet implemented")

def personStatusEffect(runObj, ID, ndx):
    obj = runObj[ID]["obj"]
    varID = getVarLinkID(obj, "Person")
    if varID:
        person = switchElem(runObj, varID, "")
        if obj["InputLinks"]["InputLink"][ndx]["Name"] == "Add":
            return person+"->StatusEffect.contains("+obj["StatusEffect"]+") == false && "+person+"->StatusEffect.add(\""+obj["StatusEffect"]+"\")"
        elif obj["InputLinks"]["InputLink"][ndx]["Name"] == "Remove":
            return person+"->StatusEffect.remove(\""+obj["StatusEffect"]+"\")"

def inventoryForm(runObj, ID, ndx):
    return "// FIXME: add code to show inventory form"

def setBoolDirectly(runObj, ID, ndx):
    obj = runObj[ID]["obj"]
    varID = getVarLinkID(obj, "Var")
    if varID:
        return "Schedule.insert(date_today.addDays("+switchElem(runObj, varID, "")+"))"
    else:
        raise Exception("Unimplemented:\n"+str(obj["VariableLinks"]["VariableLink"]))

def seqVar_reference(runObj, ID, ndx):
    obj = runObj[ID]["obj"]
    return re.sub("[. ]", "_", obj["RefFileName"].replace("\\", "::"))+"();"

def switchElem(runObj, ID, ws, ndx = None):
    if runObj[ID]["type"] == "SeqEvent":
        parseSeqEvent(runObj, ID)
    elif runObj[ID]["type"] == "SeqAct_SetAccountActive":
        return ws + setActive(runObj, ID, ndx, "Account")
    elif runObj[ID]["type"] == "SeqAct_SetRemoteSchedule":
        return ws + setRemoteSchedule(runObj, ID, ndx)
    elif runObj[ID]["type"] == "SeqVar_Reference":
        return ws + seqVar_reference(runObj, ID, ndx)
    elif runObj[ID]["type"] == "SeqAct_PersonStatusEffect":
        return ws + personStatusEffect(runObj, ID, ndx)
    elif runObj[ID]["type"] == "SeqVar_Double":
        return ws + SeqVar_Double(runObj, ID, ndx)
    elif runObj[ID]["type"] == "SeqVar_Player":
        return ws + "player"
    elif runObj[ID]["type"] == "SeqAct_AcceptEvent":
        return ws + "true"
    elif runObj[ID]["type"] == "SeqActLat_InventoryForm":
        return ws + inventoryForm(runObj, ID, ndx)
    elif runObj[ID]["type"] == "SeqAct_SetRuleActive":
        return ws + setActive(runObj, ID, ndx, "Rule")
    elif runObj[ID]["type"] == "SeqAct_SetBoolDirectly":
        return ws + setBoolDirectly(runObj, ID, ndx)
    else:
        raise Exception("Not yet implemented:"+runObj[ID]["type"])

def addRunObj(runObj, obj, ET):
    ID = int(obj["ID"])
    while ID >= len(runObj):
        runObj.append(None)

    if runObj[ID] is not None:
        raise Exception("Duplicate ID:"+obj["ID"])
    runObj[ID] = {"type": ET, "obj": obj}

def main(argv):
    inputfile = ''
    try:
        opts, args = getopt.getopt(argv, "hi:", ["ifile=", "ofile="])
    except getopt.GetoptError:
        print('eventToPy.py -i <inputfile>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('eventToPy.py -i <inputfile>')
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
    with open(inputfile) as infile:
        jsonObj = json.load(infile)
    m = re.match(r"^.*Schools/NormalSchool/(.*)/([^/]+)\.ve\.json$", inputfile)
    if m == None:
        raise Exception("unexpected json input path")

    print("namespace "+re.sub("[. ]", "_", m.group(1).replace("/", "::"))+" {")
    print("void "+re.sub("[. ]", "_", m.group(2))+"()\n{")

    runObj = []
    if "VisualEvent" in jsonObj:
        for tp in ["SeqObjects", "SeqVars"]:
            if tp in jsonObj["VisualEvent"] and jsonObj["VisualEvent"][tp] is not None:
                for ET, el in jsonObj["VisualEvent"][tp].items():
                    if type(el) == list:
                        for obj in el:
                            addRunObj(runObj, obj, ET)
                    else:
                        addRunObj(runObj, el, ET)

        if runObj[0]["type"] != "SeqEvent":
            if runObj[0]["type"] == "EventChain":  # occurs 3 times
                raise Exception("not yet implemented")
            raise Exception("Expected SeqEvent as ID 0")

        switchElem(runObj, 0, "")
    print("}\n}")
#    print(json.dumps(jsonObj, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
