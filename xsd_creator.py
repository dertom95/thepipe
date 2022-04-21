from xml.dom import minidom

class XSDCreator:
    def __init__(self,xsd_name):
        self.enum_types={}
        self.xml_doc=minidom.Document()
        
        self.namespace="https://%s.com" % xsd_name
        self.xml_root = self.xml_doc.createElement("xs:schema")
        self.xml_root.setAttribute('xmlns:xs','http://www.w3.org/2001/XMLSchema')
        self.xml_root.setAttribute('targetNamespace',self.namespace)
        self.xml_root.setAttribute('xmlns',self.namespace)
        self.xml_root.setAttribute('elementFormDefault',"qualified")

        self.xml_doc.appendChild(self.xml_root)


    def create_enum_type(self,name,enum_values,strict=False):
        if name in self.enum_types:
            #raise KeyError("EnumType:%s already defined" % name)
            print("EnumType:%s already defined" % name)
            return
		# <xs:union>
		# 	<xs:simpleType>
		# 		<xs:restriction base="xs:string">
		# 			<xs:enumeration value="float"/>
		# 			<xs:enumeration value="int"/>
		# 			<xs:enumeration value="string"/>
		# 		</xs:restriction>
		# 	</xs:simpleType>
		# 	<xs:simpleType>
		# 		<xs:restriction base="xs:string">
		# 		</xs:restriction>
		# 	</xs:simpleType>
		# </xs:union>
        enum_type = self.xml_doc.createElement("xs:simpleType")
        enum_type.setAttribute('name',name)
        enum_type.setAttribute('final','restriction') # what is this for?
        self.xml_root.appendChild(enum_type)
        self.enum_types[name]=enum_type

        current_elem = enum_type

        if not strict:
            union = self.xml_doc.createElement("xs:union")
            string_type = self.xml_doc.createElement("xs:simpleType")

            enum_restriction = self.xml_doc.createElement("xs:restriction")
            enum_restriction.setAttribute("base","xs:string")
            string_type.appendChild(enum_restriction)
            union.appendChild(string_type)

            enum_inner_type = self.xml_doc.createElement("xs:simpleType")
            union.appendChild(enum_inner_type)
            
            current_elem = enum_inner_type
            enum_type.appendChild(union)

        enum_restriction = self.xml_doc.createElement("xs:restriction")
        enum_restriction.setAttribute("base","xs:string")
        current_elem.appendChild(enum_restriction)

        for value in enum_values:
            enum_value = self.xml_doc.createElement("xs:enumeration")
            enum_value.setAttribute("value",value)
            enum_restriction.appendChild(enum_value)

        return enum_type

    def add_attribute(self,current_block,name,required=False,name_type="xs:string"):
        attribs,_=current_block
        xml_attrib = self.xml_doc.createElement("xs:attribute")
        xml_attrib.setAttribute("name",name)
        xml_attrib.setAttribute("type",name_type)
        if required:
            xml_attrib.setAttribute("use","required")

        # TODO: required
        attribs.appendChild(xml_attrib)
        return current_block        

    def create_block(self,current_block,elem_name,type_name=None,allow_content=False):
        if not current_block:
            xml_current=self.xml_root
        else:
            attribs,xml_current=current_block        
        xml_elem = self.xml_doc.createElement("xs:element")
        xml_elem.setAttribute("name",elem_name)

        xml_current.appendChild(xml_elem)
        xml_current = xml_elem

        if type_name:
            xml_elem.setAttribute("type",type_name)
            return xml_current,None

        xml_complex = self.xml_doc.createElement("xs:complexType")
        if allow_content:
            xml_complex.setAttribute("mixed","true")
            
        xml_current.appendChild(xml_complex)
        xml_current = xml_complex

        xml_choice = self.xml_doc.createElement("xs:choice")
        xml_choice.setAttribute("minOccurs","0")
        xml_choice.setAttribute("maxOccurs","unbounded")
        xml_current.appendChild(xml_choice)
        xml_subblocks = xml_choice

        return xml_complex,xml_subblocks

    def create_type(self,type_name,allow_content=False):
        xml_complex = self.xml_doc.createElement("xs:complexType")
        xml_complex.setAttribute("name",type_name)
        
        if allow_content:
            xml_complex.setAttribute("mixed","true")
            
        self.xml_root.appendChild(xml_complex)

        xml_choice = self.xml_doc.createElement("xs:choice")
        xml_choice.setAttribute("minOccurs","0")
        xml_choice.setAttribute("maxOccurs","unbounded")
        xml_complex.appendChild(xml_choice)
        xml_subblocks = xml_choice

        return xml_complex,xml_subblocks        


    def to_string(self):
        xsd_result = self.xml_doc.toprettyxml()
        return xsd_result


