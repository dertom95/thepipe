from inspect import Attribute
import re,argparse,os,time
import shutil,copy

from sys import platform
from pathlib import Path
from xml.etree import ElementTree
from xsd_creator import XSDCreator
from tools import BoolValue, InputFile, MultiFileValue,NumberValue,FileValue,EnumValue,StringValue, VectorValue,InputFile

XMLNS=None
XMLR=None
HOST=None
ARG_AUTOCOMPLETE_REPOSITORIES=False
ARG_AUTOCOMPLETE_REPOSITORY_LEVELS=2
ARG_GENERATE_XSD=False

INPUT_TYPE_SINGLEFILE = 0
INPUT_TYPE_MULTIFILE  = 1

if platform == "linux" or platform == "linux2":
    HOST="linux"
elif platform == "darwin":
    HOST="mac"
elif platform == "win32":
    HOST="win"
else:
    raise AttributeError("Unknown platform: %s"  %  platform)

class XSDManager:
    instance=None
    files=[]

    def get():
        if not XSDManager.instance:
            XSDManager.instance=XSDManager()
        return XSDManager.instance

    def __init__(self):
        self.targets=[]
        self.creator=XSDCreator("tp-runtime")      

        main=self.creator.create_block(None,"main")
        self.creator.add_attribute(main,"target")
        self.creator.add_attribute(main,"required")

        repositories=self.creator.create_block(main,"repositories")
        filerepo=self.creator.create_block(repositories,"file-repository")
        self.creator.add_attribute(filerepo,"name",True)
        self.creator.add_attribute(filerepo,"folder",True)
        self.creator.add_attribute(filerepo,"levels")

        fr_filter=self.creator.create_block(filerepo,"filter")
        self.creator.add_attribute(fr_filter,"extension")

        self.pipeline=self.creator.create_block(main,"pipeline")
        self.creator.add_attribute(self.pipeline,"pl-name",True)
        self.creator.add_attribute(self.pipeline,"target",False,"targettype")

        p_init=self.creator.create_block(self.pipeline,"init")
        pi_eval=self.creator.create_block(p_init,"eval",None,True)

        
        file_type=self.creator.create_type("file_type")
        self.creator.add_attribute(file_type,"filename",True,"filetype" if ARG_AUTOCOMPLETE_REPOSITORIES else "xs:string")

        pi_input=self.creator.create_block(p_init,"input")
        pii_file=self.creator.create_block(pi_input,"file","file_type")

        multifile=self.creator.create_block(pi_input,"multifile")
        self.creator.add_attribute(multifile,"name",True)
        piim_file=self.creator.create_block(multifile,"file","file_type")

        #self.creator.add_attribute(pii_file,"filename",True,"filetype" if ARG_AUTOCOMPLETE_REPOSITORIES else "xs:string")

        p_eval=self.creator.create_block(self.pipeline,"eval",None,True)

        p_output=self.creator.create_block(self.pipeline,"output")
        self.creator.add_attribute(p_output,"repository")
        self.creator.add_attribute(p_output,"target")
        self.creator.add_attribute(p_output,"filename",True)

    def add_files(self,files):
        self.files.extend(files)
    
    def add_target(self,target_name):
        if target_name not in self.targets:
            self.targets.append(target_name)

    def add_converter(self,converter):
        xsdconverter=self.creator.create_block(self.pipeline,converter.qualified_name())
        for (id,output,tool_type,type_signature,description) in converter.params.values():
            if id=="in" or id=="out":
                continue
            tool_type.put_xsd(self.creator,xsdconverter,converter.qualified_name(),id)
        


    def xsdcreator_write(self,filename):
        self.creator.create_enum_type("targettype",self.targets)
        self.creator.create_enum_type("filetype",self.files)

        result=self.creator.to_string()
        print(result)

        xsd_file = open(filename,"w")
        xsd_file.write(result)
        xsd_file.close()    


def xgetrequired(xml,attrib):
    if attrib in xml.attrib:
        return xml.attrib[attrib]
    else:
        raise NameError("required attribute '%s' was not found in:\n%s" %(attrib,ElementTree.tostring(xml)))


def xget(xml,attrib,default_value=None,to_lower=False):
    result=default_value
    if attrib in xml.attrib:
        result=xml.attrib[attrib]
    if result==None:
        return None
    if to_lower:
        return result.lower()
    else:
        return result

def xget_b(xml,attrib,default_value):
    if attrib in xml.attrib:
        return xml.attrib[attrib].lower()=="true"
    else:
        return default_value

def xget_parameters(xml):
    global XMLNS
    params={}
    for param in xml.iter("%sparam"%XMLNS):
        id = xgetrequired(param,"id")
        output = xget(param,"output","")
        default_value = xget(param,"default","")
        required = xget_b(param,"required",False)
        type_signature = xget(param,"type","string",True)
        description = xget(param,"description","")
        tool_type=create_type(type_signature,default_value,required,param)
        params[id]=(id,output,tool_type,type_signature,description)
    return params

def trim_text(text):
    prefix=None
    result=""
    for line in text.split("\n"):
        if len(line)==0:
            continue
        if not prefix:
            prefix=line.replace(line.lstrip(),"")
        result+="%s\n"%line.replace(prefix,"",1)
    return result

def create_type(type_signature,default_value,required,xml_param):
    if type_signature=="bool":
        return BoolValue(default_value,required)
    elif type_signature=="string":
        return StringValue(default_value,required)
    elif type_signature.startswith("vec"):
        m=re.match(r"vec\[(.+?)\]",type_signature)
        if not m:
            raise AttributeError("Unknown vectortype:%s" % type_signature)
        dim = int(m.group(1))
        return VectorValue(dim,default_value,required)
    elif type_signature.startswith("number"):
        if type_signature=="number":
            return NumberValue(0,0,float("inf"),required)
        
        m = re.match(r"number\[([0-9.]+?)-([0-9.]+?)\]",type_signature)
        
        if m:
            from_value = m.group(1)
            to_value   = m.group(2)
            return NumberValue(default_value,from_value,to_value,required)
        else:
            raise AttributeError("Unknown number-signature:%s" % type_signature)
    elif type_signature=="file":
        return FileValue(required)
    elif type_signature.startswith("enum"):
        result_type = EnumValue(required)
        enum_pattern=r"enum\[(([\w\d]+?)(,|\]))"
        m = re.search(enum_pattern,type_signature)
        while m:
            all=m.group(1)
            enum_value=m.group(2)
            result_type.add_enum_value(enum_value)

            type_signature=type_signature.replace(all,"")
            m = re.search(enum_pattern,type_signature)
        return result_type
    elif type_signature=="multifile":
        return MultiFileValue(required)
    else:
        raise AttributeError("Unknown type:%s" % type_signature)

def walklevel(some_dir, level=1):
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:] 

class Converter:
    CONVERTERS = {}

    def __init__(self,xml):
        global XMLNS
        self.prefix = xgetrequired(xml,"prefix")
        self.name   = xgetrequired(xml,"name")
        self.target = xget(xml,"target","all")
        if ARG_GENERATE_XSD:
            XSDManager.get().add_target(self.target)        
        
        cmd = xml.find("%scommand"%XMLNS)
        if cmd is None:
            raise AttributeError("Converter without command-tag!: %s" % ElementTree.tostring(xml))

        self.tool_id = xgetrequired(cmd,"toolid")
        self.tool_args = xgetrequired(cmd,"arguments")
        self.tool_out_ext = xget(cmd,"extension",None)
        self.metafiles = xget(cmd,"metafiles",None)

        self.params = xget_parameters(xml)
        if ARG_GENERATE_XSD:
            XSDManager.get().add_converter(self)
    
    def qualified_name(self):
        return "%s-%s" % (self.prefix,self.name)

    def add(converter):
        qn = converter.qualified_name()
        if qn in Converter.CONVERTERS:
            raise KeyError("There is already a converter with the qn:%s" % qn)

        Converter.CONVERTERS[qn]=converter

    def add_from_xml(xml):
        converter = Converter(xml)
        Converter.add(converter)

    def reset_params(self):
        for key in self.params:
            id,output,tool_type,type_signature,description=self.params[key]
            tool_type.reset()

    def execute(self,context_data,counter,temp_folder,input_data,xml_data,file_history,executions):
        context,shared_locals=context_data
        input_type,name,input=input_data

        self.reset_params()
        id,output,tool_type,type_signature,description=self.params["in"]
        tool_type.set(input)

        id,output,tool_type,type_signature,description=self.params["out"]

        if input_type==INPUT_TYPE_SINGLEFILE:
            filename, file_extension = os.path.splitext(file_history[0])
            file_extension=file_extension[1:]
            filename_without_folder = os.path.basename(filename)
            if self.tool_out_ext:
                file_extension=self.tool_out_ext

            out_file = "%s%s-%s-%s.%s" %(temp_folder,str(counter).rjust(4,'0'),self.qualified_name(),filename_without_folder,file_extension)
            output_type=INPUT_TYPE_SINGLEFILE
        else:
            file_extension=self.tool_out_ext
            ttype=type(tool_type)
            if ttype==FileValue:
                out_file = "%s%s-%s-%s.%s" %(temp_folder,str(counter).rjust(4,'0'),self.qualified_name(),name,file_extension)
                tool_type.set(out_file)
                output_type=INPUT_TYPE_SINGLEFILE
            elif ttype==MultiFileValue:
                output_type=INPUT_TYPE_MULTIFILE

                # for filename in input:
                #     filename, file_extension = os.path.splitext(file_history[0])
                #     file_extension=file_extension[1:]
                #     filename_without_folder = os.path.basename(filename)
                #     if self.tool_out_ext:
                #         file_extension=self.tool_out_ext

                #     out_file = "%s%s-%s-%s.%s" %(temp_folder,str(counter).rjust(4,'0'),self.qualified_name(),filename_without_folder,file_extension)
                # TODO
                pass

        for attrib in xml_data.attrib:
            if attrib in self.params:
                value = xml_data.attrib[attrib]
                id,output,tool_type,type_signature,description=self.params[attrib]
                tool_type.set(value)
        
        tool = Tool.get(self.tool_id)

        arguments = self.tool_args

        for p in self.params:
            (id,output,tool_type,type_signature,description) = self.params[p]
            if not tool_type.value_set():
                continue
            
            direct_tag = r"@[%s]"%id
            param_output = tool_type.output(output)
            if direct_tag in arguments:
                arguments=arguments.replace(direct_tag,param_output)
            else:
                arguments=arguments.replace("@@","%s @@" % param_output)

        arguments=context.resolve_variables_in_string(arguments,shared_locals)
        arguments=arguments.replace("@@","")


        # let the Tool do the execution(!)
        retcode,execution_call = tool.execute(arguments)
        executions.append(execution_call)

        file_history.append(out_file)

        return retcode,output_type,out_file,file_extension,self.metafiles
        
        

    
    def get(qn):
        if qn not in Converter.CONVERTERS:
            return None
            #raise KeyError("there is no converter with the qn:%s" % qn)

        return Converter.CONVERTERS[qn]

    def has(qn):
        return qn in Converter.CONVERTERS

class Tool:
    TOOLS={}

    def __init__(self,xml):
        global XMLNS
        print(ElementTree.tostring(xml))
        self.xml=xml
        self.tool_type=xgetrequired(xml,"type")
        self.tool_id=xgetrequired(xml,"id")
        self.version=xget(xml,"version","unknown")
        self.is_default=xget_b(xml,"default",False)
        self.target=xget(xml,"target","all")
        if ARG_GENERATE_XSD:
            XSDManager.get().add_target(self.target)

        self.command=None
        for cmd in xml.iter("%scommand"%XMLNS):
            host = xgetrequired(cmd,"host")
            if host!=HOST:
                # ignore tools for other HOSTs
                continue

            if self.tool_type=="cli":
                file = xgetrequired(cmd,"file")
                self.command=file.replace("@",os.getcwd())
            else:
                raise AttributeError("Unknown ToolType:%s" % self.tool_type)

    def qualified_name(self):
        return "%s.%s" % (self.tool_id,self.version)

    def add(tool):
        tid=tool.tool_id

        if  tid not in Tool.TOOLS:
            Tool.TOOLS[tid]={}
        tool_bag = Tool.TOOLS[tid]
        if tool.version in tool_bag:
            raise NameError("[%s] There was already a version %s registered!" % ( tid,tool.version ))

        tool_bag[tool.version]=tool
        if "default" not in tool_bag or tool.is_default:
            tool_bag["default"]=tool

    def get(tool_id,version="default"):
        # TODO: handle versions
        if tool_id not in Tool.TOOLS:
            raise KeyError("Unknown tool with tool_id: %s" % tool_id)
        
        return Tool.TOOLS[tool_id][version]

    # def get_command(self):
    #     if HOST not in self.commands:
    #         raise KeyError("[Tool:%s] Not command for OS[%s]" % (self.tool_id,HOST))
    #     return self.commands[HOST]

    def add_from_xml(xml):
        tool = Tool(xml)
        Tool.add(tool)

    def execute(self,arguments):
        execution_command = "%s %s" % (self.command,arguments)
        print(execution_command)
        retcode = os.system(execution_command)

        return retcode,execution_command

class FileRepository:
    IGNORE_FOLDERS=["__pycache__",".venv",".vscode","temp",".git"]
    def __init__(self,repo_name,folder):
        self.folder=folder
        self.name=repo_name
        self.filters=[]
    
    def get_file(self,input):
        # repo,all=FileRepository.get_repo_from_file(input)
        # if repo!=self.name:
        #     raise AttributeError("FileRepo[%s]. Tried to locate file from other filerepo!:%s" % (self.folder,input))

        # input = input.replace(all,"")

        filename="%s/%s" % (self.folder,input)
        if not os.path.exists(filename):
            raise AttributeError("FileRepo[%s]. Could not locate file:%s" % (self.folder,input))

        return os.path.abspath(filename)

    def add_filter(self,folder_filter,filename_filter,extension_filter):
        def filter(folder,filename,extension):
            if folder_filter and re.match(folder_filter,folder) is None:
                return False
            if filename_filter and re.match(filename_filter,filename) is None:
                return False
            if extension_filter and re.match(extension_filter,extension) is None:
                return False
            return True
        
        self.filters.append(filter)

    def write_file(self,input,output_in_repo):
        output_filename="%s/%s" % (self.folder,output_in_repo)
        directory = os.path.dirname(output_filename)
        try:
            os.makedirs(directory)
        except:
            pass
        shutil.copyfile(input,output_filename)

    def is_valid_folder(self,folder):
        if folder in FileRepository.IGNORE_FOLDERS:
            return False
        for invalid_folder in FileRepository.IGNORE_FOLDERS:
            if folder.startswith(invalid_folder):
                return False

        return True

    def execute_filer(self,folder,filename,extension):
        for filter in self.filters:
            if not filter(folder,filename,extension):
                return False
        return True

    def get_all_files(self):
        listOfFiles = []
        for (dirpath, dirnames, filenames) in walklevel(self.folder,ARG_AUTOCOMPLETE_REPOSITORY_LEVELS):
            rel_folder = os.path.relpath(dirpath,self.folder)
            if not self.is_valid_folder(rel_folder):
                continue
            if rel_folder==".":
                rel_folder=""

            repodir="%s://%s" % (self.name,rel_folder)

            if len(self.filters)>0:
                for file in filenames:
                    filename, file_extension = os.path.splitext(file)
                    if self.execute_filer(rel_folder,filename,file_extension[1:]):
                        listOfFiles.append(os.path.join(repodir, file))
            else:
                listOfFiles += [os.path.join(repodir, file) for file in filenames]        
        return listOfFiles

    def get_repo_from_file(input):
        m=re.search(r"(.+?)://",input)
        if m is None:
            raise AttributeError("Could not filter file-repository:%s" % input)

        all=m.group(0)
        repo=m.group(1)
        return repo,all




class Context:
    def __init__(self,args):
        global ARG_AUTOCOMPLETE_REPOSITORIES,ARG_AUTOCOMPLETE_REPOSITORY_LEVELS,ARG_GENERATE_XSD

        self.input_files = args.input
        self.keep_intermediate = args.keep_intermediate_files
        ARG_AUTOCOMPLETE_REPOSITORIES = args.autocomplete_repositories
        ARG_AUTOCOMPLETE_REPOSITORY_LEVELS = args.autocomplete_repository_levels
        ARG_GENERATE_XSD = args.generate_xsd

        self.repositories={}

    def add_repository_from_xml(self,xml):
        name = xgetrequired(xml,"name")

        if name in self.repositories:
            raise AttributeError("Repositiory with name:%s already present!" % name)

        if xml.tag=="%sfile-repository"%XMLR:
            name = xgetrequired(xml,"name")
            folder = xgetrequired(xml,"folder")
            file_repo = FileRepository(name,folder)
            self.repositories[name]=file_repo

            for filter in xml.iter("%sfilter"%XMLR):
                filter_folder   = xget(filter,"folder",None)
                filter_filename = xget(filter,"filename",None) 
                filter_extension= xget(filter,"extension",None)
                file_repo.add_filter(filter_folder,filter_filename,filter_extension)

            if ARG_AUTOCOMPLETE_REPOSITORIES and ARG_GENERATE_XSD:
                files = file_repo.get_all_files()
                XSDManager.get().add_files(files)
        
    
    def get_repository(self,repo_name):
        return self.repositories[repo_name]

    def retrieve_input(self,xml_input):
        tag = xml_input.tag.lower().replace(XMLR,"")
        if tag=="file":
            filename = xgetrequired(xml_input,"filename")
            repo_name,all = FileRepository.get_repo_from_file(filename)
            input_file = InputFile(self,filename,repo_name).retrieve()
            return (INPUT_TYPE_SINGLEFILE,repo_name,input_file)
        elif tag=="multifile":
            multifile_name=xgetrequired(xml_input,"name")
            result=[]
            for xml_file in xml_input:
                tag=xml_file.tag.lower().replace(XMLR,"")
                if tag!="file":
                    raise AttributeError("Invalid element in multifile:%s\n%s"%(tag,ElementTree.tostring(xml_file)))
                
                filename = xgetrequired(xml_file,"filename")
                repo_name,all = FileRepository.get_repo_from_file(filename)
                input_file = InputFile(self,filename,repo_name).retrieve()
                result.append((repo_name,input_file))
            return (INPUT_TYPE_MULTIFILE,multifile_name,result)
        else:
            raise AttributeError("Unknown input-type:%s" % tag)

    def resolve_variables_in_string(self,string_data,shared_locals):
        pattern = r"@\[(.+?)\]"
        m = re.search(pattern,string_data)
        while m:
            all = m.group(0)
            var_name = m.group(1)
            if var_name in shared_locals:
                data = shared_locals[var_name]
                string_data=string_data.replace(all,str(data))
            m = re.search(pattern,string_data)

        if "@[" in string_data:
            raise AttributeError("Could not resolve all variables:%s" % string_data)

        return string_data

    def resolve_attribute_variables(self,xml,shared_locals):
        for attrib in xml.attrib:
            resolved = self.resolve_variables_in_string(xml.attrib[attrib],shared_locals)
            xml.attrib[attrib]=resolved

    def execute_pipeline(self,xml_pipeline):
        shared_globals=dict()
        shared_locals=dict()

        execution_calls=[]

        target = xget(xml_pipeline,"target","all")

        pipeline_name = xgetrequired(xml_pipeline,"pl-name")

        pipeline_folder = "temp/%s%s/" % (pipeline_name,time.time())
        try:
            os.makedirs(pipeline_folder)
        except:
            pass

        shared_locals["target"]=target
        shared_locals["temp-folder"]=pipeline_folder

        init=xml_pipeline.find("%sinit"%XMLR)
        if init is None:
            raise AttributeError("Pipeline without init:\n%s" % ElementTree.tostring(xml_pipeline))

        for ev in init.iter("%seval"%XMLR):
            ev_str = trim_text(ev.text)
            exec(ev_str,shared_globals,shared_locals)
            execution_calls.append("eval start:\n%s\neval end:------" % ev_str)

        xml_input=init.find("%sinput"%XMLR)
        if xml_input is None:
            raise AttributeError("Pipeline.Init without <input/>\n%s" % ElementTree.tostring(xml_pipeline))
        
        command_counter=1
        for _input in xml_input:
            
            metafiles=[]
            input_type,name,input = input_data = self.retrieve_input(_input)
            if input_type==INPUT_TYPE_SINGLEFILE:
                shared_locals["init-input_type"]="single_file"
                shared_locals["init-repo_name"]=name
                
                file_history=[input]
                execution_calls.append("\nInput-File:%s" %input)

                shared_locals["init-full-filename"]=input
                in_file = os.path.basename(input)
                filename_wo_ext, file_extension = os.path.splitext(in_file)
                file_extension=file_extension[1:]
                shared_locals["init-filename"]=in_file
                shared_locals["init-file-wo-ext"]=filename_wo_ext
                shared_locals["init-file-ext"]=file_extension
            elif input_type==INPUT_TYPE_MULTIFILE:
                file_history=[input]
                shared_locals["init-input-type"]="multi_file"
                shared_locals["init-mf-name"]=name
                shared_locals["init-mf-files"]=input
            else:
                raise AttributeError("Unknown input_type:%s [%s]" % (input_type,ElementTree.tostring(_input)))


            # execute pipeline for every input
            for _command in xml_pipeline:
                command = copy.deepcopy(_command)
                if input_type==INPUT_TYPE_SINGLEFILE:
                    shared_locals["full-filename"]=input
                    in_file = os.path.basename(input)
                    filename_wo_ext, file_extension = os.path.splitext(in_file)
                    file_extension=file_extension[1:]
                    shared_locals["filename"]=in_file
                    shared_locals["file-wo-ext"]=filename_wo_ext
                    shared_locals["file-ext"]=file_extension
                else:
                    shared_locals["input-type"]="multi_file"
                    shared_locals["mf-name"]=name
                    shared_locals["mf-files"]=input


                tag = command.tag.lower().replace(XMLR,"")
                if tag=="init":
                    continue

                ## CONVERTER ##
                converter = Converter.get(tag)
                if converter:
                    self.resolve_attribute_variables(command,shared_locals)
                    result,input_type,input,file_extension,_metafiles = converter.execute((self,shared_locals),command_counter,pipeline_folder,input_data,command,file_history,execution_calls)
                    if _metafiles:
                        _metafiles=self.resolve_variables_in_string(_metafiles,shared_locals)
                        for mf in _metafiles.split(','):
                            if mf not in metafiles:
                                metafiles.append(mf)

                    command_counter+=1
                    shared_locals["file-ext"]=file_extension
                    if result!=0:
                        raise AttributeError("command resulted in error!")
                ## PYTHON-EVAL ##
                elif tag=="eval":
                    ev_str = trim_text(command.text)
                    exec(ev_str,shared_globals,shared_locals)
                    execution_calls.append("eval start:\n%s\neval end:------" % ev_str)
                ## OUTPUT / COPY ##
                elif tag=="output":
                    name=xget(command,"repository","cwd")
                    filename=xgetrequired(command,"filename")
                    target_before=target
                    target=xget(command,"target",target)
                    copy_metafiles=xget_b(command,"copy_metafiles",True)

                    shared_locals["target"]=target

                    filename=self.resolve_variables_in_string(filename,shared_locals)

                    repo = self.get_repository(name)
                    repo.write_file(input,filename)
                    if copy_metafiles:
                        folder=os.path.dirname(filename)
                        for mf in metafiles:
                            filename="%s/%s" % (folder,os.path.basename(mf))
                            repo.write_file(mf,filename)

                    execution_calls.append("output:%s => [%s]:%s" % (input,name,filename))
                    target=target_before
                    shared_locals["target"]=target                    
                else:
                    raise AttributeError("Unknown pipeline-command:%s"%tag)

        execution_file = open("%s%s-exe-list.%s.txt" % (pipeline_folder,pipeline_name,time.time()),"w")
        execution_text = "\n".join(execution_calls)        
        execution_file.write(execution_text)
        execution_file.close()

        if not self.keep_intermediate:
            shutil.rmtree(pipeline_folder)


    def execute_file(self,filename):
        xml = ElementTree.parse(filename).getroot()
        global XMLR
        XMLR=namespace(xml)        

        repos = xml.find("%srepositories"%XMLR)
        if repos is not None:
            for repo in repos:
                self.add_repository_from_xml(repo)
        default_repo=self.repositories["cwd"]=FileRepository("cwd",os.getcwd())
        if ARG_AUTOCOMPLETE_REPOSITORIES and ARG_GENERATE_XSD:
            files = default_repo.get_all_files()
            XSDManager.get().add_files(files)        

        for pipeline in xml.iter("%spipeline"%XMLR):
            self.execute_pipeline(pipeline)
                

    def run(self):
        for file in self.input_files:
            self.execute_file(file)


def namespace(element):
    m = re.match(r'\{.*\}', element.tag)
    return m.group(0) if m else ''

def load_plugins(folder="plugins"):
    xml_files = Path(folder).rglob("*.xml")
    xml_element_tree = None
    for xml_file in xml_files:
        data = ElementTree.parse(xml_file).getroot()
        if xml_element_tree is None:
            xml_element_tree=data
        else:
            xml_element_tree.extend(data)
    return xml_element_tree

def parse_tools(xml_data):
    global XMLNS
    XMLNS=namespace(xml_data)

    print(ElementTree.tostring(xml_data))
    for tool in xml_data.iter("%stool"%XMLNS):
        Tool.add_from_xml(tool)

    for converter in xml_data.iter("%sconverter"%XMLNS):
        Converter.add_from_xml(converter)

def parse_arguments():
    parser = argparse.ArgumentParser(description="thepipeline - universal assets processor")
    parser.add_argument("--input",action="append",help="input xml-files", required=True)
    parser.add_argument("--keep-intermediate-files",type=bool,default=False,help="keep files generated during runtime")
    parser.add_argument("--autocomplete-repositories",type=bool,default=False,help="iterates over repositories for autocompletion")
    parser.add_argument("--autocomplete-repository-levels",type=int,default=2,help="folder depth to use")
    parser.add_argument("--generate-xsd",type=bool,default=False,help="generate runtime.xsd (default:plugins/tpruntime.xsd)")
    args = parser.parse_args()

    ctx = Context(args)
    return ctx

def execute_context(ctx):
    pass    

def startup():
    ctx = parse_arguments()
    xml = load_plugins()
    parse_tools(xml)

    ctx.run()
        

    if ARG_GENERATE_XSD:
        XSDManager.get().xsdcreator_write("plugins/tpruntime.xsd")

startup()