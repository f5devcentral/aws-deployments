when RULE_INIT {
    expr srand("[clock clicks]")
    set static::TARGET_VIP "/Common/Vip1_demo_iApp.app/Vip1_demo_iApp_vs"
}
when CLIENT_ACCEPTED {

    set a [expr int(223*rand())]
    set b [expr int(255*rand())]
    set c [expr int(255*rand())]
    set d [expr int(255*rand())]

    while { $a == 192 || $a == 172 || $a == 10 } {
        #log local0. "changing first octet from $a"
        set a [expr int(223*rand())]
    }
    #log local0. $a.$b.$c.$d
    snat $a.$b.$c.$d

    virtual $static::TARGET_VIP
}
